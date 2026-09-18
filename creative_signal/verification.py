from __future__ import annotations

import json
import re
import posixpath
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, unquote, urlencode, parse_qs

from .common import canonical_url, domain, normal, parse_date, same_domain, valid_web_url


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.structured = [], [], []
        self.hidden = 0
        self.capture = False
        self.script_parts = []
        self.controls, self.open_controls = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.capture, self.script_parts = True, []
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in {"a", "button"}:
            enabled = "disabled" not in attrs and attrs.get("aria-disabled") != "true" and "hidden" not in attrs and attrs.get("aria-hidden") != "true"
            actionable = tag == "button" or bool(attrs.get("href"))
            self.open_controls.append({"tag": tag, "enabled": enabled and actionable and not self.hidden,
                                       "parts": [], "label": attrs.get("aria-label", ""),
                                       # Teamtailor permits custom button text (e.g. "Join us!").
                                       # Its explicit job-application action is stronger than that label.
                                       "job_application_action": tag == "button" and any(
                                           x.endswith("->careersite--jobs--form-overlay#showFormOverlay")
                                           for x in attrs.get("data-action", "").split())})

    def handle_endtag(self, tag):
        if tag in {"a", "button"} and self.open_controls and self.open_controls[-1]["tag"] == tag:
            self.controls.append(self.open_controls.pop())
        if tag == "script" and self.capture:
            try:
                self.structured.append(json.loads("".join(self.script_parts)))
            except ValueError:
                pass
            self.capture = False
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if self.capture:
            self.script_parts.append(data)
        if not self.hidden:
            self.parts.append(data)
            for control in self.open_controls:
                control["parts"].append(data)

    @property
    def text(self):
        return normal(" ".join(self.parts))

    @property
    def application_offered(self):
        labels = {"apply", "apply now", "apply here", "apply for this job", "apply for this position",
                  "apply for this role", "apply to this job", "submit application"}
        return any(c["enabled"] and (c["job_application_action"] or any(normal(s).lower() in labels for s in
                   [" ".join(c["parts"]), c["label"]])) for c in self.controls)


def parse_page(text: str) -> PageParser:
    p = PageParser()
    p.feed(text)
    return p


def title_matches(a: str, b: str) -> bool:
    left, right = set(re.findall(r"[a-z0-9]+", a.lower())), set(re.findall(r"[a-z0-9]+", b.lower()))
    return bool(left and right and len(left & right) / max(len(left), len(right)) >= 0.7)


def job_schemas(value):
    if isinstance(value, list):
        for child in value:
            yield from job_schemas(child)
    elif isinstance(value, dict):
        kind = value.get("@type")
        if kind == "JobPosting" or isinstance(kind, list) and "JobPosting" in kind:
            yield value
        if "@graph" in value:
            yield from job_schemas(value["@graph"])


def workday_api(url: str) -> str | None:
    p = urlparse(url)
    if not p.hostname or not p.hostname.endswith(".myworkdayjobs.com"):
        return None
    bits = p.path.strip("/").split("/")
    if "job" not in bits:
        return None
    job_index = bits.index("job")
    if job_index < 1:
        return None
    site, tenant = bits[job_index - 1], p.hostname.split(".")[0]
    path = "/".join(bits[job_index:]).removesuffix("/apply")
    return f"https://{p.hostname}/wday/cxs/{tenant}/{site}/{path}"


def parse_posting(response: dict, job: dict, clock=None) -> dict:
    clock = clock or datetime.now(timezone.utc)
    base = {"status": "needs_review", "availability": "unknown", "url": response["url"],
            "checked_at": response.get("checked_at"), "description": "", "reason": "No matching structured job posting", "evidence_file": response.get("evidence_file")}
    if response.get("http_status") != 200:
        return {**base, "reason": "Employer page unavailable; do not interpret this as a closed vacancy"}
    raw = response.get("text", "")
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = {}
    info = payload.get("jobPostingInfo") if isinstance(payload, dict) else None
    if isinstance(info, dict):
        if not title_matches(job["title"], info.get("title", "")):
            return {**base, "reason": "Employer posting title does not match the discovered role"}
        if info.get("posted") is False or info.get("canApply") is False:
            return {**base, "status": "closed", "reason": "Employer reports the vacancy is unavailable"}
        return {**base, "status": "employer_verified", "availability": "confirmed_open" if info.get("posted") is True and info.get("canApply") is True else "unknown",
                "description": parse_page(info.get("jobDescription", "")).text, "posted_at": info.get("startDate"),
                "employer_job_id": info.get("jobReqId"), "reason": "Matched employer hiring-system record"}
    page = parse_page(raw)
    if any(x in page.text.lower() for x in ["this job is no longer available", "this position has been filled", "no longer accepting applications"]):
        return {**base, "status": "closed", "reason": "Employer page reports the vacancy is unavailable"}
    for schema in job_schemas(page.structured):
        if not title_matches(job["title"], schema.get("title", "")):
            continue
        through = parse_date(schema.get("validThrough"))
        if through and through < clock:
            return {**base, "status": "closed", "reason": "Employer validThrough date has passed"}
        description = parse_page(schema.get("description") or "").text
        if len(description) < 100:
            return {**base, "reason": "Employer description is too short to verify responsibilities"}
        offered = schema.get("directApply") is True or page.application_offered
        return {**base, "status": "employer_verified", "availability": "application_offered" if offered else "unknown",
                "description": description, "posted_at": schema.get("datePosted"),
                "reason": "Matched employer JobPosting; application link presence is not a guarantee the vacancy is unfilled"}
    return base


def prefix_matches(url: str, prefix: str) -> bool:
    a, b = urlparse(url), urlparse(prefix)
    path = posixpath.normpath(unquote(a.path)).rstrip("/")
    root = posixpath.normpath(unquote(b.path)).rstrip("/")
    return a.scheme == b.scheme and a.hostname == b.hostname and (path == root or path.startswith(root + "/"))


def eightfold_details_url(response: dict, job: dict) -> str | None:
    """Use the public job-detail route used by an identified Eightfold careers page."""
    raw = response.get("text", "")
    p = urlparse(response["url"])
    match = re.fullmatch(r"/careers/job/(\d+)(?:-[^/]*)?/?", p.path)
    if response.get("http_status") != 200 or not match or not same_domain(response["url"], job["domain"]):
        return None
    if not re.search(r'id=[\"\x27]pcsx[\"\x27]', raw) or "/gen/js/pcsxPwa." not in raw:
        return None
    return f"{p.scheme}://{p.netloc}/api/pcsx/position_details?" + urlencode({
        "position_id": match[1], "domain": job["domain"], "hl": "en"})


def eightfold_application_offered(response: dict, details_url: str, job: dict) -> bool:
    if response.get("http_status") != 200 or canonical_url(response["url"]) != canonical_url(details_url):
        return False
    try:
        payload = json.loads(response.get("text", ""))
    except ValueError:
        return False
    if not isinstance(payload, dict) or payload.get("status") != 200:
        return False
    data, metadata, error = payload.get("data"), payload.get("metadata") or {}, payload.get("error") or {}
    if not isinstance(data, dict) or not isinstance(metadata, dict) or not isinstance(error, dict):
        return False
    if metadata.get("isFallback") or error.get("message") or error.get("body"):
        return False
    expected = parse_qs(urlparse(details_url).query).get("position_id", [None])[0]
    public_url = data.get("publicUrl") or ""
    public_id = re.fullmatch(r"/careers/job/(\d+)(?:-[^/]*)?/?", urlparse(public_url).path)
    if str(data.get("id")) != expected or not public_id or public_id[1] != expected:
        return False
    if not same_domain(public_url, job["domain"]) or not title_matches(job["title"], data.get("name", "")):
        return False
    actions = data.get("positionUserActions") or {}
    action = actions.get("applyAction") if isinstance(actions, dict) else None
    return isinstance(action, dict) and action.get("status") == "allowed"


class Verifier:
    def __init__(self, transport, config):
        self.transport, self.config = transport, config
        self.clock = None

    def verify(self, job: dict) -> dict:
        company_domain = job["domain"]
        trusted = self.config["checks"].get("trusted_careers", {}).get(company_domain, [])
        urls = job["apply_urls"][:3]
        allowed = [u for u in urls if same_domain(u, company_domain) or any(prefix_matches(u, p) for p in trusted)]
        if not allowed:
            # Establish hosted-board ownership from an actual corporate link, not a job-board flag.
            home = self.transport.web("https://" + company_domain)
            if home.get("http_status") == 200 and same_domain(home["url"], company_domain):
                links = [urljoin(home["url"], link) for link in parse_page(home["text"]).links]
                career_links = [u for u in links if any(w in u.lower() for w in ["career", "jobs", "greenhouse", "workday", "lever.co"])][:2]
                for link in career_links:
                    if same_domain(link, company_domain):
                        page = self.transport.web(link)
                        if page.get("http_status") == 200 and same_domain(page["url"], company_domain):
                            links.extend(urljoin(page["url"], x) for x in parse_page(page["text"]).links)
                allowed = [u for u in urls if any(prefix_matches(u, link) and domain(link) != company_domain
                           and urlparse(link).path.strip("/") for link in links)]
        if not allowed:
            return {"status": "needs_review", "availability": "unknown", "description": "", "url": "", "reason": "No employer-controlled application route established"}
        result = None
        for url in allowed[:2]:
            try:
                valid_web_url(url)
            except ValueError:
                continue
            target = workday_api(url) or url
            response = self.transport.web(target)
            final_host = domain(response["url"])
            if final_host != domain(target) and not same_domain(response["url"], company_domain):
                continue
            if not same_domain(response["url"], company_domain) and canonical_url(response["url"]) != canonical_url(target):
                # A redirect between tenants on the same hiring platform is not ownership proof.
                continue
            result = parse_posting(response, job, self.clock)
            result["application_url"] = url
            if result["status"] == "employer_verified" and result["availability"] == "unknown":
                details_url = eightfold_details_url(response, job)
                if details_url:
                    details = self.transport.web(details_url)
                    result["application_evidence_file"] = details.get("evidence_file")
                    if eightfold_application_offered(details, details_url, job):
                        result["availability"] = "application_offered"
                        result["reason"] += "; matching public employer record explicitly allows the application action"
            if result["status"] in {"employer_verified", "closed"}:
                return result
        return result or {"status": "needs_review", "availability": "unknown", "description": "", "url": "", "reason": "Employer route could not be verified"}
