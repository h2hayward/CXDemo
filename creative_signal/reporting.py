from __future__ import annotations

import csv
import html
import re
from collections import Counter
from urllib.parse import quote

from .common import normal, valid_web_url, write_json


def status_label(value):
    return value.replace("_", " ").capitalize()


def safe_cell(value):
    text = str(value) if value is not None else ""
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def md(value):
    text = html.escape(normal(value), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~])", r"\\\1", text)


def link(url, label="source"):
    try:
        valid_web_url(url)
    except (ValueError, TypeError):
        return "Unavailable source URL"
    return f"[{md(label)}](<{quote(url, safe=':/?=&%#@+;,-._~')}>)"


def brief(a, demo=False, evidence_replay=False):
    job, posting, analysis = a["job"], a.get("posting", {}), a.get("analysis", {})
    listing = posting.get("source_kind") == "job_listing"
    hiring_source = (f"Job listing: {link(posting.get('url', ''), 'read listing')} · Source: {md(job.get('source', 'discovery'))}. Employer website verification: not requested."
                     if listing else f"Employer posting: {link(posting.get('url', ''), 'read evidence')} · Content: {md(posting.get('status', 'unchecked'))} · Availability: {md(posting.get('availability', 'unknown'))}")
    rows = [f"# {md(a['company'])}", "", "**SYNTHETIC DEMO — fictional company, role, people and ad records. No live research.**" if demo else "Private account research — review before contact.", "",
            f"Status: **{md(status_label(a['status']))}** · Evidence points: {a['score']}/8 (not a purchase probability).", "",
            f"Vacancy: {md(job['title'])} · {md(job['location'])} · {md(job['country'])}", "",
            hiring_source, "",
            f"Checked: {md(posting.get('checked_at', 'unknown'))}. Posted: {md(a.get('freshness', {}).get('date') or posting.get('posted_at') or job.get('posted_at') or 'unknown')}.", "",
            "## What the source says", ""]
    if evidence_replay:
        rows[2] = "**REPROCESSED LIVE EVIDENCE — real saved responses, reprocessed after fixes. No fresh acquisition during replay; this is not a clean end-to-end pass.**"
    rows += [f"> {md(q)}" for q in analysis.get("evidence_quotes", [])]
    if not analysis.get("evidence_quotes"):
        rows.append("No qualifying source quote has been established.")
    if analysis.get("scope_quote"):
        rows += ["", "Coordination scope:", "", "> " + md(analysis["scope_quote"])]
    if analysis.get("reporting_line_quote"):
        rows += ["", "Reporting relationship stated in the vacancy:", "", "> " + md(analysis["reporting_line_quote"])]
    rows += ["", "## Advertising evidence", ""]
    ads = a.get("ads")
    if ads:
        rows += [f"Meta · country scope {md(ads['scope'])} · checked {md(ads['checked_at'])} · {md(ads['status'])}.", "",
                 f"Provider-reported count: {ads['provider_reported_count'] if ads['provider_reported_count'] is not None else 'unknown'}. Unique active records returned: {ads['returned_unique_active_ads']}. Matched to the account: {ads['matched_active_ads']}. Result complete: {'yes' if ads['complete'] else 'no'}.", "",
                 md(ads["reason"]), ""]
        if ads.get("access_provider") == "Apify":
            rows += [f"Apify sample: at most {ads.get('sample_limit')} records. Dataset rows returned: {ads.get('raw_dataset_rows') if ads.get('raw_dataset_rows') is not None else 'not run'}. This is a capped sample, not a total ad count.", ""]
            identity = ads.get("identity") or {}
            if identity.get("page_url"):
                rows += ["Advertiser page: " + link(identity["page_url"], "corporate-linked or reviewed Facebook page") + ". " + md(identity.get("basis", "")), ""]
            elif identity.get("search_url"):
                rows += ["Meta search: " + link(identity["search_url"], "company-name search") + ". " + md(identity.get("basis", "")), ""]
        rows += [f"- {link(ad['source_url'], 'Meta library record ' + ad['ad_id'])}; landing page {link(ad['landing_url'], 'company domain')}" for ad in ads["examples"]]
    else:
        rows.append("Not checked: earlier qualification was incomplete or the run stopped.")
    rows += ["", "## Who to investigate", "", "Target role: " + md(a.get("target_role", "Resolve after qualifying the employer responsibilities.")), ""]
    for person in a["people"]["candidates"]:
        rows += [f"- {md(person['name'])}, {md(person['title'])}, {md(person['country'])} — {link(person['profile_url'], 'profile')}. Provider reports a current role; remit and reporting relationship unconfirmed."]
    if not a["people"]["candidates"]:
        rows.append("No named person qualified or this stage was skipped.")
    rows += ["", "## Why CreativeX could be relevant", "", md(a["conversation_angle"] or "Insufficient verified evidence for a conversation angle."), "",
             "This is a relevance hypothesis. Hiring and advertising do not establish a broken process, missing software, new budget or purchase intent.", "",
             "## Draft conversation starter", "",
             md(a.get("conversation_starter") or "No draft: hiring evidence has not passed the required checks."), "",
             "A source-based draft for review; it does not establish that the selected person owns this work.", "",
             "## Suggested approach", "",
             "Use the specific responsibility and territory in the listing quote. Confirm whether the candidate owns that work. Explore which repeatable digital-asset checks or creative measurements matter to them. Avoid claims about ad spend, poor creative or wasted budget.", "",
             "Next action: " + md(a["next_action"]), "", "## Still to check", ""]
    rows += ["- " + md(gap) for gap in a["gaps"]]
    rows += ["", "## How it ranked", ""] + [f"- {md(reason)}: +{points}" for reason, points in a["score_basis"]]
    evidence = list(dict.fromkeys([job.get("discovery_evidence"), job.get("analysis_evidence"), posting.get("evidence_file"), posting.get("application_evidence_file"), a.get("analysis_evidence"), a.get("ads", {}).get("evidence_file"), *a.get("ads", {}).get("evidence_files", []), *a["people"].get("evidence_files", [])]))
    rows += ["", "## Saved evidence", ""] + [f"- [{path}](../{path})" for path in evidence if path]
    return "\n".join(rows) + "\n"


def export_results(output, manifest, jobs, accounts):
    output.mkdir(parents=True, exist_ok=True)
    demo = manifest["mode"] == "synthetic_demo"
    ready = sum(a["status"] == "priority_review" for a in accounts)
    manifest["outcome"] = {
        "priority_review_accounts": ready,
        "yield_status": "candidates_for_review" if ready else "no_qualifying_briefs",
        "live_validation": "not_applicable_synthetic" if demo else (
            "not_passed_run_halted" if manifest["state"] != "complete" else
            "pending_independent_checks" if ready else "failed_yield"
        ),
    }
    write_json(output / "manifest.json", manifest)
    write_json(output / "results.json", {"mode": manifest["mode"], "state": manifest["state"], "outcome": manifest["outcome"], "accounts": accounts, "jobs": jobs})
    with (output / "accounts.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["mode", "company", "domain", "status", "evidence_points", "vacancy", "hiring_source_url", "hiring_source_kind", "employer_url", "meta_scope", "provider_reported_ads", "returned_active_ads", "matched_active_ads", "complete_ads_result", "possible_owner", "owner_title", "owner_profile", "conversation_angle", "conversation_starter", "next_action", "gaps"])
        for a in accounts:
            ads = a.get("ads", {})
            person = next(iter(a["people"]["candidates"]), {})
            posting = a.get("posting", {})
            source_kind = posting.get("source_kind", "employer_website")
            writer.writerow([safe_cell(v) for v in [manifest["mode"], a["company"], a["domain"], a["status"], a["score"], a["job"]["title"], posting.get("url"), source_kind, posting.get("url") if source_kind == "employer_website" else "", ads.get("scope"), ads.get("provider_reported_count"), ads.get("returned_unique_active_ads"), ads.get("matched_active_ads"), ads.get("complete"), person.get("name"), person.get("title"), person.get("profile_url"), a["conversation_angle"], a.get("conversation_starter"), a["next_action"], " | ".join(a["gaps"])]])
            path = output / "briefs" / (a["id"] + ".md")
            path.parent.mkdir(exist_ok=True)
            path.write_text(brief(a, demo, manifest["mode"] == "live_evidence_replay"), encoding="utf-8")
    states = Counter(j["status"] for j in jobs)
    rows = ["# CreativeX hiring research", "", "**SYNTHETIC DEMO — canned provider responses, no live research or network calls.**" if demo else "Private research output. Review account eligibility and evidence before contact.", "",
            f"Execution state: **{md(manifest['state'])}**. {len(jobs)} discovered records; {len(accounts)} accounts examined; {ready} ready for priority review.", ""]
    if manifest["mode"] == "live_evidence_replay":
        rows[2] = "**REPROCESSED LIVE EVIDENCE — real saved responses, reprocessed after fixes. No fresh acquisition during replay; this is not a clean end-to-end pass.**"
    if not ready:
        rows += ["**No qualifying briefs. This run did not demonstrate the complete workflow.**", ""]
        if not jobs and manifest["state"] == "complete":
            rows += ["Discovery returned no vacancies. Employer verification, model analysis, advertising and people lookup were not reached. This does not establish that no relevant employers are hiring.", ""]
    elif not demo:
        rows += ["**Independent validation pending.** Check native ad evidence and current person/remit before calling the live proof passed.", ""]
    if manifest.get("error"):
        rows += ["Run halted: " + md(manifest["error"]), "", "These are partial results. Inspect receipts before starting a new run; requests are never retried automatically.", ""]
    rows += ["## Account queue", "", "| Account | Status | Evidence points | Brief |", "|---|---|---:|---|"]
    rows += [f"| {md(a['company'])} | {md(status_label(a['status']))} | {a['score']}/8 | [Open brief](briefs/{a['id']}.md) |" for a in accounts]
    rows += ["", "## What happened to the vacancies", ""] + [f"- {md(k)}: {v}" for k, v in sorted(states.items())]
    rows += ["", "| Company | Vacancy | Outcome | Reason |", "|---|---|---|---|"]
    rows += [f"| {md(j['company'])} | {md(j['title'])} | {md(j['status'])} | {md(j['reason'])} |" for j in jobs]
    rows += ["", "`results.json` contains all decisions and exact quotes; `accounts.csv` is the review queue. `evidence/` preserves responses and `receipts/` records API calls. `manifest.json` records the scope and call usage.", "",
             "Priority review means relevant evidence and a possible owner were found. It does not mean send-ready, confirmed buying intent, or a confirmed CreativeX prospect.", ""]
    (output / "report.md").write_text("\n".join(rows), encoding="utf-8")
