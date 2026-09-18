from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .analysis import Analyzer, AnalysisRejected, product_bridge, conversation_starter
from .common import canonical_url, normal, now, parse_date, stable_id, write_json
from .config import plan
from .http import RunHalted
from .providers import jsearch, normalize_job, meta_ads, normalize_ads, find_people, normalize_people
from .verification import Verifier


def account_domain(value, config):
    for owner, aliases in config.get("accounts", {}).get("aliases", {}).items():
        if value == owner or value in aliases:
            return owner
    return value


def freshness(value, clock, max_days):
    date = parse_date(value)
    if not date:
        return "unknown"
    if date > clock + timedelta(days=1):
        return "future"
    return "fresh" if clock - date <= timedelta(days=max_days) else "stale"


def dedupe_keys(job):
    # A role syndicated under another board ID should still be counted once.
    keys = [("role", job["domain"] or normal(job["company"]).lower(), normal(job["title"]).lower(), job["country"], normal(job["location"]).lower())]
    if job["id"]:
        keys.append(("id", job["id"]))
    keys += [("url", canonical_url(u)) for u in job["apply_urls"] if u]
    return keys


def run_pipeline(config, transport, output, *, demo=False, clock=None, progress=None):
    clock = clock or datetime.now(timezone.utc)
    progress = progress or (lambda message: None)
    verify_employer = config["checks"].get("verify_employer", False)
    analyzer, verifier = Analyzer(transport, config), Verifier(transport, config)
    verifier.clock = clock
    jobs, accounts, seen = [], [], set()
    manifest = {"version": "0.1.0", "mode": "synthetic_demo" if demo else "live",
                "started_at": now(), "evaluation_date": clock.isoformat(), "state": "running",
                "plan": plan(config), "config": config, "network_calls": 0 if demo else None,
                "notice": "All companies, people, ads and model responses are synthetic fixtures." if demo else "Private research; account eligibility and contact ownership require review."}
    write_json(output / "manifest.json", manifest)

    def persist():
        from .reporting import export_results
        manifest["counts"] = dict(transport.counts)
        manifest["finished_at"] = now()
        export_results(output, manifest, jobs, accounts)

    try:
        for country in config["discovery"]["countries"]:
            for query in config["discovery"]["queries"]:
                progress(f"Discovering vacancies: {query} / {country}")
                data = jsearch(transport, query, country, config["discovery"]["date_posted"])
                for raw in data["jobs"]:
                    job = normalize_job(raw)
                    job["account_domain"] = account_domain(job["domain"], config)
                    job["query"], job["search_country"] = query, country
                    job["discovery_evidence"] = f"evidence/jsearch-{transport.counts['jsearch']:04d}.json"
                    job["record_id"] = stable_id([job["id"], job["domain"], job["title"], job["location"], len(jobs)])
                    job["status"], job["reason"] = "discovered", ""
                    jobs.append(job)
                    keys = dedupe_keys(job)
                    if any(key in seen for key in keys):
                        job.update(status="duplicate", reason="Same vacancy ID, application URL or employer/title/location already seen")
                    seen.update(keys)
        includes = {account_domain(x, config) for x in config.get("accounts", {}).get("include_domains", [])}
        excludes = {account_domain(x, config) for x in config.get("accounts", {}).get("exclude_domains", [])}
        analysed = 0
        candidates = []
        for job in jobs:
            if job["status"] == "duplicate":
                continue
            d = job["account_domain"]
            if d in excludes or includes and d not in includes:
                job.update(status="excluded", reason="Configured exclusion or outside named-account list")
                continue
            if not d:
                job.update(status="needs_review", reason="Corporate domain unavailable; no speculative company join")
                continue
            age = freshness(job["posted_at"], clock, config["checks"]["max_job_age_days"])
            if age in {"stale", "future"}:
                job.update(status="rejected", reason=f"Discovery posting date is {age}")
                continue
            if len(normal(job["description"])) < 100:
                job.update(status="needs_review", reason="Full job description missing or too short")
                continue
            if analysed >= config["discovery"]["max_jobs"]:
                job.update(status="capped", reason="Description analysis cap reached")
                continue
            analysed += 1
            job["status"] = "analysis_pending"
            progress(f"Reading responsibilities: {job['company']} / {job['title']}")
            try:
                analysis = analyzer.analyze(job, job["description"])
            except AnalysisRejected as exc:
                job.update(status="needs_review", reason=str(exc),
                           analysis_evidence=f"evidence/llm-{transport.counts['llm']:04d}.json")
                continue
            job["discovery_analysis"] = analysis
            job["analysis_evidence"] = f"evidence/llm-{transport.counts['llm']:04d}.json"
            if analysis["decision"] == "not_relevant" or analysis["company_kind"] in {"agency", "staffing"}:
                job.update(status="rejected", reason=analysis["reason"])
            elif analysis["decision"] != "relevant":
                job.update(status="needs_review", reason=analysis["reason"])
            else:
                job.update(status="candidate", reason="Relevant job listing; account research follows")
                candidates.append(job)
        candidates.sort(key=lambda j: (j["discovery_analysis"]["company_kind"] != "advertiser", not bool(j["discovery_analysis"]["scope_quote"]), j["account_domain"], j["record_id"]))
        selected = set()
        for job in candidates:
            d = job["account_domain"]
            if d in selected or len(selected) >= config["discovery"]["max_accounts"]:
                job.update(status="capped", reason="One strongest vacancy per account and a bounded number of accounts; this role was not enriched")
                continue
            selected.add(d)
            account = {"id": stable_id(d), "company": job["company"], "domain": d,
                       "job": job, "status": "needs_review", "score": 0, "score_basis": [],
                       "gaps": ["Confirm account/customer status, territory ownership and existing opportunities in CreativeX's records."],
                       "next_action": "Review missing evidence.", "conversation_angle": "", "people": {"candidates": []}}
            accounts.append(account)
            if verify_employer:
                progress(f"Checking employer evidence: {job['company']}")
                posting = verifier.verify(job)
                posting["source_kind"] = "employer_website"
                account["posting"] = posting
                if posting["status"] != "employer_verified":
                    account["status"] = "rejected" if posting["status"] == "closed" else "needs_review"
                    account["gaps"].append(posting["reason"])
                    job.update(status=account["status"], reason=posting["reason"])
                    continue
                try:
                    primary = analyzer.analyze(job, posting["description"])
                except AnalysisRejected as exc:
                    account["analysis_evidence"] = f"evidence/llm-{transport.counts['llm']:04d}.json"
                    account["gaps"].append(str(exc))
                    job.update(status="needs_review", reason=str(exc))
                    continue
                account["analysis_evidence"] = f"evidence/llm-{transport.counts['llm']:04d}.json"
            else:
                posting = {"status": "listing_sourced", "source_kind": "job_listing",
                           "availability": "not_checked", "url": job.get("listing_url") or job["discovery_url"],
                           "description": job["description"], "posted_at": job["posted_at"],
                           "checked_at": manifest["started_at"], "evidence_file": job["discovery_evidence"],
                           "reason": "Hiring signal taken from the discovered job listing; employer website check disabled."}
                account["posting"] = posting
                primary = job["discovery_analysis"]
                account["analysis_evidence"] = job["analysis_evidence"]
            account["analysis"] = primary
            if primary["decision"] == "not_relevant" or primary["company_kind"] in {"agency", "staffing"}:
                account["status"] = "rejected"
                account["gaps"].append("Hiring description did not qualify: " + primary["reason"])
                job.update(status="rejected", reason=primary["reason"])
                continue
            account["score_basis"].append(["Employer description obtained" if verify_employer else "Job listing and source retained", 2])
            if primary["decision"] != "relevant" or primary["company_kind"] != "advertiser":
                account["gaps"].append("Listed responsibilities or own-brand advertiser status are uncertain.")
            if not primary["scope_quote"]:
                account["gaps"].append("No explicit evidence of multi-market, brand, channel or team coordination.")
            age = freshness(posting.get("posted_at") or job["posted_at"], clock, config["checks"]["max_job_age_days"])
            account["freshness"] = {"status": age, "date": posting.get("posted_at") or job["posted_at"],
                                    "source": "employer" if verify_employer and posting.get("posted_at") else "discovery"}
            if age != "fresh" or verify_employer and posting["availability"] == "unknown":
                account["gaps"].append("Vacancy date needs confirmation." if not verify_employer else "Vacancy freshness or application availability needs confirmation.")
            if len(account["gaps"]) > 1:
                job.update(status="needs_review", reason="Hiring evidence incomplete; enrichment skipped")
                continue
            account["score_basis"] += [["Relevant responsibilities with exact source quotes", 2], ["Explicit coordination scope", 1],
                                       ["Fresh posting with application availability" if verify_employer else "Recent listing date", 1]]
            account["conversation_angle"] = product_bridge(primary["signal"])
            account["conversation_starter"] = conversation_starter(job, primary)
            account["target_role"] = primary["reporting_line_quote"] or ("Head/Director of Creative Operations or Brand Marketing" if primary["signal"] == "creative_governance" else "Head/Director of Creative Effectiveness, Marketing Measurement or Media")
            aliases = config.get("accounts", {}).get("aliases", {}).get(d, [])
            progress(f"Checking Meta advertising: {job['company']}")
            ads = normalize_ads(meta_ads(transport, d, config["checks"]["meta_country"], config["checks"], aliases, company_name=job["company"]), d, aliases, config["checks"]["meta_country"])
            account["ads"] = ads
            if ads["access_provider"] == "Adyntel":
                ads["evidence_file"] = f"evidence/ads-{transport.counts['ads']:04d}.json"
            if ads["status"] != "observed_active":
                account["gaps"].append(ads["reason"])
                account["next_action"] = "Check Meta page identity and ad activity; people lookup skipped until advertising evidence is usable."
                job.update(status="needs_review", reason="Relevant hiring; advertising evidence unresolved")
                continue
            account["score_basis"].append(["Active Meta records with matching landing domain", 1])
            account["gaps"].append("Spot-check linked ads in Meta's native library; counts do not show spend, total creative volume or buying intent.")
            progress(f"Finding possible functional owners: {job['company']}")
            before_people = transport.counts["blitz"]
            people = normalize_people(find_people(transport, d, job["country"], config["checks"]["people_per_account"]), d, aliases, job["country"], config["checks"]["recommended_people"], primary["signal"], primary["reporting_line_quote"])
            people["evidence_files"] = [f"evidence/blitz-{i:04d}.json" for i in range(before_people + 1, transport.counts["blitz"] + 1)]
            account["people"] = people
            if people["candidates"]:
                account["score_basis"].append(["Possible current functional owner found", 1])
                account["status"] = "priority_review"
                account["next_action"] = "Review evidence and account eligibility; confirm the person's remit and reporting relationship before preparing outreach."
            else:
                account["gaps"].append("No sufficiently matched functional owner in the bounded people results.")
                account["next_action"] = "Resolve the current owner of the target role and review account eligibility."
            job.update(status=account["status"], reason="Hiring signal and advertising checked; see account brief")
        manifest["state"] = "complete"
    except KeyboardInterrupt:
        manifest["state"] = "halted"
        manifest["error"] = "Interrupted. An in-flight request may have been billed; inspect receipts before rerunning."
    except (RunHalted, ValueError, KeyError, TypeError, AttributeError) as exc:
        manifest["state"] = "halted"
        # Never copy arbitrary provider objects or credentials into an error report.
        manifest["error"] = str(exc) if isinstance(exc, RunHalted) else f"Unexpected response/configuration shape ({type(exc).__name__}); inspect saved evidence before rerunning."
    finally:
        for account in accounts:
            account["score"] = sum(points for _, points in account["score_basis"])
        accounts.sort(key=lambda a: (a["status"] != "priority_review", -a["score"], a["domain"]))
        persist()
    return {"manifest": manifest, "jobs": jobs, "accounts": accounts}
