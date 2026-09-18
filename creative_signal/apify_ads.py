"""Bounded Meta sampling through Apify; no subscription or credit purchases."""
from __future__ import annotations

import re
from decimal import Decimal
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from .common import same_domain, write_json, normal
from .http import RunHalted
from .verification import parse_page

ACTOR = "apify~facebook-ads-scraper"
BUILD = "0.0.378"
POLL_LIMIT = 8
DATASET_READS_PER_RUN = 3  # Metadata, items, and one delayed-metadata readback.
TERMINAL = {"SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"}


def facebook_page_url(value):
    """Recognise page links, excluding shares, groups, login and search URLs."""
    if not isinstance(value, str):
        return None
    p = urlparse(value)
    if p.scheme not in {"http", "https"} or p.username or p.password or p.port not in {None, 80, 443}:
        return None
    if p.hostname not in {"facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com"}:
        return None
    path = p.path.strip("/")
    if path == "profile.php":
        page_id = parse_qs(p.query).get("id", [""])[0]
        return "https://www.facebook.com/" + page_id if page_id.isdigit() else None
    blocked = {"sharer", "sharer.php", "share", "share.php", "dialog", "login", "login.php", "ads", "groups", "events", "watch", "reel", "reels", "search", "plugins", "help", "privacy", "policies", "pages"}
    if re.fullmatch(r"[A-Za-z0-9._-]+", path) and path.lower() not in blocked:
        return "https://www.facebook.com/" + path.lower()
    return None


def resolve_page(transport, account_domain, checks, aliases=()):
    configured = checks.get("facebook_pages", {}).get(account_domain)
    if configured:
        return {"page_url": facebook_page_url(configured), "basis": "operator-reviewed company/page mapping", "evidence_files": []}
    home = transport.web("https://" + account_domain)
    evidence = [home["evidence_file"]] if home.get("evidence_file") else []
    if home.get("http_status") != 200 or not any(same_domain(home["url"], d) for d in [account_domain, *aliases]):
        return {"page_url": None, "reason": "Corporate website unavailable or redirected outside the reviewed account domains; Meta page unresolved", "evidence_files": evidence}
    links = {facebook_page_url(urljoin(home["url"], link)) for link in parse_page(home["text"]).links}
    links.discard(None)
    if len(links) != 1:
        return {"page_url": None, "reason": "Expected one corporate-linked Facebook page; none or multiple found. Add a reviewed page mapping before sampling.", "evidence_files": evidence}
    return {"page_url": links.pop(), "basis": "Facebook page linked by the corporate website", "corporate_url": home["url"], "evidence_files": evidence}


def run_data(response, expected_id=None):
    data = response.get("data")
    if not isinstance(data, dict) or not re.fullmatch(r"[A-Za-z0-9]+", str(data.get("id", ""))):
        raise RunHalted("Apify run response has no usable run ID; reconcile the started request before rerunning")
    if expected_id and data["id"] != expected_id:
        raise RunHalted("Apify status response returned a different run ID")
    return data


def convert_rows(rows, page_url, company_name=None):
    converted = []
    for ad in rows:
        if not isinstance(ad, dict):
            raise RunHalted("Apify dataset contains a non-object record")
        if ad.get("error") or ad.get("errorMessage"):
            raise RunHalted("Apify reported a scraping error in the dataset; inspect saved evidence")
        snapshot = ad.get("snapshot") or {}
        if not isinstance(snapshot, dict):
            raise RunHalted("Apify ad snapshot has an unexpected shape")
        profile = facebook_page_url(snapshot.get("pageProfileUri"))
        page_id = str(ad.get("pageID") or ad.get("pageId") or snapshot.get("pageId") or "")
        ids = {str(v) for v in [ad.get("pageID"), ad.get("pageId"), snapshot.get("pageId")] if v is not None}
        # A numeric profile and a vanity URL cannot be equated without evidence.
        page_name = ad.get("pageName") or snapshot.get("pageName") or ""
        if page_url:
            same_page = page_id.isdigit() and len(ids) == 1 and (profile == page_url or page_url.rsplit("/", 1)[-1] == page_id)
        else:
            # A search result needs both a matching advertiser name here and a
            # matching destination domain in normalize_ads. No page ownership claim.
            name_key = lambda s: re.sub(r"[^a-z0-9]", "", normal(s).lower())
            same_page = (page_id.isdigit() and len(ids) == 1 and bool(company_name)
                         and name_key(page_name) == name_key(company_name))
            if profile and profile.rsplit("/", 1)[-1].isdigit():
                same_page = same_page and profile.rsplit("/", 1)[-1] == page_id
        cards = snapshot.get("cards") or []
        if not isinstance(cards, list):
            raise RunHalted("Apify ad cards have an unexpected shape")
        converted.append({
            "ad_archive_id": str(ad.get("adArchiveID") or ad.get("adArchiveId") or ""),
            "is_active": ad.get("isActive"), "page_id": page_id,
            "_page_identity_matches": same_page,
            "snapshot": {"page_name": page_name,
                         "link_url": snapshot.get("linkUrl") or "",
                         "cards": [{"link_url": c.get("linkUrl") or ""} for c in cards if isinstance(c, dict)]},
        })
    return converted


def verified_empty_page(rows, page_url):
    """The actor emits a page-summary row when it finds no ads, rather than []."""
    if len(rows) != 1 or not isinstance(rows[0], dict):
        return False
    row = rows[0]
    info = row.get("pageInfo") or {}
    if not isinstance(info, dict):
        return False
    page = info.get("page") or {}
    return (isinstance(page, dict) and str(page.get("id", "")).isdigit()
            and facebook_page_url(row.get("inputUrl")) == page_url
            and type(row.get("totalCount")) is int and row["totalCount"] == 0
            and row.get("results") == [] and row.get("isResultComplete") is True
            and info.get("xfbAdLibraryIsCaptchaRequired") is False
            and not row.get("error") and not row.get("errorMessage"))


def fetch_ads(transport, account_domain, country, checks, aliases=(), company_name=None):
    # Direct Facebook Page inputs use the actor's all-country scope. Do not
    # silently advertise support for a geography the request cannot express.
    if country != "ALL":
        raise RunHalted("Apify page sampling currently supports meta_country=ALL only")
    if checks.get("ad_lookup") == "company_search":
        if not company_name:
            raise RunHalted("Meta company search requires the discovered employer name")
        search_url = "https://www.facebook.com/ads/library/?" + urlencode({
            "active_status": "active", "ad_type": "all", "country": country,
            "q": company_name, "search_type": "keyword_exact_phrase", "media_type": "all"})
        identity = {"page_url": None, "search_url": search_url, "company_name": company_name,
                    "basis": "Meta Ad Library exact company-name search; require matching page name and ad destination domain. Page ownership is not independently verified.",
                    "evidence_files": []}
    else:
        identity = resolve_page(transport, account_domain, checks, aliases)
    evidence = list(identity["evidence_files"])
    base = {"results": [], "country_code": country, "_access_provider": "Apify",
            "_identity": identity, "_evidence_files": evidence,
            "_sample_limit": checks["ads_per_account"], "is_result_complete": False}
    input_url = identity["page_url"] or identity.get("search_url")
    if not input_url:
        return {**base, "_reason": identity["reason"]}
    limits = getattr(transport, "limits", {})
    if "apify_dataset" in limits and limits["apify_dataset"] - transport.counts.get("apify_dataset", 0) < DATASET_READS_PER_RUN:
        raise RunHalted("Insufficient dataset-read budget for another actor; no paid run started")
    limit = checks["ads_per_account"]
    ceiling = Decimal(str(checks["apify_max_charge_usd"]))
    headers = {"Authorization": "Bearer " + transport.credential("APIFY_TOKEN")}
    params = {"build": checks.get("apify_build", BUILD), "waitForFinish": 0,
              "timeout": 180, "memory": 1024, "restartOnError": "false",
              "maxTotalChargeUsd": str(ceiling)}
    body = {"startUrls": [{"url": input_url}], "resultsLimit": limit,
            "activeStatus": "active", "onlyTotal": False, "includeAboutPage": False,
            "isDetailsPerAd": False, "enrichWithEcommerceData": False}
    response = transport.api("ads", "https://api.apify.com/v2/acts/" + ACTOR + "/runs?" + urlencode(params), headers=headers, body=body)
    evidence.append(f"evidence/ads-{transport.counts['ads']:04d}.json")
    run = run_data(response)
    run_id = run["id"]
    # Persist the ID immediately: a later failure must never start another run.
    run_path = transport.output / "apify-runs" / (run_id + ".json")
    write_json(run_path, {"run_id": run_id, "account_domain": account_domain, "input": body,
                          "charge_ceiling_usd": str(ceiling), "status": run.get("status"), "evidence_files": evidence})
    for _ in range(POLL_LIMIT):
        if run.get("status") in TERMINAL:
            break
        response = transport.api("apify_status", f"https://api.apify.com/v2/actor-runs/{run_id}?waitForFinish=25", headers=headers)
        evidence.append(f"evidence/apify_status-{transport.counts['apify_status']:04d}.json")
        run = run_data(response, run_id)
    write_json(run_path, {"run_id": run_id, "account_domain": account_domain, "input": body,
                          "charge_ceiling_usd": str(ceiling), "status": run.get("status"),
                          "usage_total_usd_preliminary": run.get("usageTotalUsd"), "evidence_files": evidence})
    if run.get("status") != "SUCCEEDED":
        raise RunHalted(f"Apify run {run_id} did not succeed; inspect its saved run record. No replacement run was started.")
    dataset_id = run.get("defaultDatasetId", "")
    if not re.fullmatch(r"[A-Za-z0-9]+", str(dataset_id)):
        raise RunHalted("Apify completed without a usable dataset ID")
    # Read metadata as well as bounded rows, so truncation cannot hide an overrun.
    metadata = transport.api("apify_dataset", f"https://api.apify.com/v2/datasets/{dataset_id}", headers=headers)
    evidence.append(f"evidence/apify_dataset-{transport.counts['apify_dataset']:04d}.json")
    count = metadata.get("data", {}).get("itemCount")
    if type(count) is not int or not 0 <= count <= limit:
        raise RunHalted("Apify dataset size is missing or exceeds the approved record cap")
    rows = transport.api("apify_dataset", f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json&clean=true&limit={limit}", headers=headers, response_type="list")
    evidence.append(f"evidence/apify_dataset-{transport.counts['apify_dataset']:04d}.json")
    rows_evidence = evidence[-1]
    if len(rows) > limit:
        raise RunHalted("Apify returned more rows than the approved record cap")
    if len(rows) > count:
        # Dataset metadata can lag a completed run. Reconcile the same dataset
        # once inside the shared read budget; never start a replacement actor.
        metadata = transport.api("apify_dataset", f"https://api.apify.com/v2/datasets/{dataset_id}", headers=headers)
        evidence.append(f"evidence/apify_dataset-{transport.counts['apify_dataset']:04d}.json")
        count = metadata.get("data", {}).get("itemCount")
        if type(count) is not int or not 0 <= count <= limit:
            raise RunHalted("Reconciled Apify dataset size is missing or exceeds the approved record cap")
    # A completed dataset's metadata can still lag its items endpoint. Preserve
    # that discrepancy without discarding observed evidence. Both counts are
    # bounded above; this sample never claims a complete account ad inventory.
    if len(rows) < count:
        raise RunHalted("Apify dataset returned fewer rows than its recorded size")
    dataset_observation = {"_raw_dataset_rows": len(rows), "_dataset_metadata_count": count,
                           "_dataset_metadata_lagged": count != len(rows)}
    if identity["page_url"] and verified_empty_page(rows, identity["page_url"]):
        return {**base, "number_of_ads": 0, "_evidence_files": evidence,
                "_primary_evidence": rows_evidence,
                "_run_id": run_id, **dataset_observation, "_page_matched_rows": 0,
                "_checked_at": run.get("finishedAt"),
                "_usage_total_usd_preliminary": run.get("usageTotalUsd"),
                "_reason": "Apify reported no ads for this corporate-linked Facebook page. Other brand pages, markets and platforms remain unchecked."}
    converted = convert_rows(rows, identity["page_url"], company_name=company_name)
    return {**base, "results": converted, "_evidence_files": evidence,
            "_primary_evidence": rows_evidence, "_run_id": run_id,
            "_checked_at": run.get("finishedAt"),
            **dataset_observation, "_page_matched_rows": sum(r["_page_identity_matches"] for r in converted),
            "_usage_total_usd_preliminary": run.get("usageTotalUsd"),
            "_reason": "No active ad records matched both the advertiser identity and the account landing domain in this bounded sample"}
