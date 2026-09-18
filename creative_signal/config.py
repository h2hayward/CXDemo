from __future__ import annotations

import math
import tomllib
from pathlib import Path

from .common import public_company_domain, valid_web_url, domain


def load_config(path: Path) -> dict:
    with path.open("rb") as f:
        c = tomllib.load(f)
    d, checks = c["discovery"], c["checks"]
    if type(checks.get("verify_employer", False)) is not bool:
        raise ValueError("verify_employer must be true or false")
    if checks.get("ad_lookup", "corporate_page") not in {"corporate_page", "company_search"}:
        raise ValueError("ad_lookup must be corporate_page or company_search")
    if c["analysis"].get("provider", "openai") not in {"openai", "azure"}:
        raise ValueError("analysis.provider must be openai or azure")
    if c["analysis"].get("reasoning_effort") not in {None, "none", "minimal", "low", "medium", "high"}:
        raise ValueError("Invalid reasoning effort")
    if not d["queries"] or not d["countries"] or len(d["queries"]) > 12 or len(d["countries"]) > 10:
        raise ValueError("Provide 1–12 queries and 1–10 countries")
    if not all(isinstance(q, str) and 0 < len(q.strip()) <= 150 for q in d["queries"]):
        raise ValueError("Queries must be nonempty strings up to 150 characters")
    if not all(isinstance(x, str) and len(x) == 2 and x.isalpha() for x in d["countries"]):
        raise ValueError("Use two-letter country codes (gb for the UK)")
    for key, section, low, high in [
        ("pages_per_query", d, 1, 1), ("max_jobs", d, 1, 200), ("max_accounts", d, 1, 50),
        ("max_job_age_days", checks, 1, 90), ("max_description_chars", checks, 1000, 40000),
        ("people_per_account", checks, 1, 50), ("recommended_people", checks, 1, 5),
        ("max_output_tokens", c["analysis"], 500, 4000),
    ]:
        value = section[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{key} must be an integer between {low} and {high}")
    if d["date_posted"] not in {"today", "3days", "week", "month"}:
        raise ValueError("date_posted must be today, 3days, week or month")
    if checks["meta_country"] != "ALL" and (len(checks["meta_country"]) != 2 or not checks["meta_country"].isalpha()):
        raise ValueError("meta_country must be ALL or one two-letter code")
    provider = checks.get("ad_provider", "adyntel")
    if provider not in {"apify", "adyntel"}:
        raise ValueError("ad_provider must be apify or adyntel")
    if provider == "apify":
        import re
        from .apify_ads import facebook_page_url
        if checks["meta_country"] != "ALL":
            raise ValueError("Apify page sampling currently requires meta_country=ALL")
        limit, cap = checks.get("ads_per_account"), checks.get("apify_max_charge_usd")
        if type(limit) is not int or not 1 <= limit <= 25:
            raise ValueError("Apify sample must contain 1–25 ads per account")
        if type(cap) not in {float, int} or not math.isfinite(cap) or not 0.0058 <= cap <= 0.145:
            raise ValueError("Apify charge ceiling must be between $0.0058 and $0.145 per account")
        if not re.fullmatch(r"\d+\.\d+\.\d+", checks.get("apify_build", "")):
            raise ValueError("Pin apify_build to a reviewed build number")
        for owner, page in checks.get("facebook_pages", {}).items():
            if public_company_domain(owner) != owner or not facebook_page_url(page):
                raise ValueError("Facebook mappings require a corporate domain and a reviewed Facebook page URL")
    for name in ["include_domains", "exclude_domains"]:
        for value in c.get("accounts", {}).get(name, []):
            if public_company_domain(value) != value:
                raise ValueError(f"{name} must contain plain corporate domains")
    for key, value in c.get("costs", {}).items():
        if not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid cost rate: {key}")
    aliases = c.get("accounts", {}).get("aliases", {})
    claimed = set(aliases)
    for owner, values in aliases.items():
        if public_company_domain(owner) != owner or not isinstance(values, list):
            raise ValueError("Aliases need a corporate domain and a list of related domains")
        for value in values:
            if public_company_domain(value) != value or value in claimed:
                raise ValueError("Alias domains must be valid and map to exactly one account")
            claimed.add(value)
    for owner, prefixes in checks.get("trusted_careers", {}).items():
        if public_company_domain(owner) != owner or not isinstance(prefixes, list):
            raise ValueError("Trusted careers need a corporate domain and a list of URLs")
        for prefix in prefixes:
            valid_web_url(prefix)
            from urllib.parse import urlparse
            parsed = urlparse(prefix)
            if parsed.query or parsed.fragment or (domain(prefix) in {"boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.lever.co"} and not parsed.path.strip("/")):
                raise ValueError("Trusted careers must identify the employer's board, not a shared service root")
    return c


def call_limits(c: dict) -> dict:
    d = c["discovery"]
    verify_employer = c["checks"].get("verify_employer", False)
    limits = {"jsearch": len(d["queries"]) * len(d["countries"]) * d["pages_per_query"],
            "ads": d["max_accounts"], "blitz": d["max_accounts"] * 2,
            "llm": d["max_jobs"] + (d["max_accounts"] if verify_employer else 0),
            "public_web": d["max_accounts"] * 6 if verify_employer else 0}
    if c["checks"].get("ad_provider") == "apify":
        from .apify_ads import POLL_LIMIT, DATASET_READS_PER_RUN
        limits.update(apify_status=d["max_accounts"] * POLL_LIMIT, apify_dataset=d["max_accounts"] * DATASET_READS_PER_RUN)
        if c["checks"].get("ad_lookup") != "company_search":
            limits["public_web"] += d["max_accounts"]
    return limits


def plan(c: dict) -> dict:
    limits = call_limits(c)
    rates = c.get("costs", {})
    costs = {"jsearch_max_usd": limits["jsearch"] * rates["jsearch_request_usd"]} if "jsearch_request_usd" in rates else {}
    if "adyntel_credit_usd" in rates:
        costs["adyntel_max_usd"] = limits["ads"] * rates["adyntel_credit_usd"]
    if c["checks"].get("ad_provider") == "apify":
        costs.pop("adyntel_max_usd", None)
        costs["apify_max_charge_usd"] = round(limits["ads"] * c["checks"]["apify_max_charge_usd"], 6)
    return {
        "queries": [{"query": q, "country": country} for country in c["discovery"]["countries"] for q in c["discovery"]["queries"]],
        "limits": limits,
        "max_jobs_reviewed": c["discovery"]["max_jobs"], "max_accounts": c["discovery"]["max_accounts"],
        "max_people_records": c["discovery"]["max_accounts"] * c["checks"]["people_per_account"],
        "meta_scope": c["checks"]["meta_country"],
        "ad_provider": c["checks"].get("ad_provider", "adyntel"),
        "analysis_provider": c["analysis"].get("provider", "openai"),
        "verify_employer": c["checks"].get("verify_employer", False),
        "ad_lookup": c["checks"].get("ad_lookup", "corporate_page"),
        "max_ad_records": limits["ads"] * c["checks"].get("ads_per_account", 0) if c["checks"].get("ad_provider") == "apify" else None,
        "known_variable_cost_estimates": costs,
        "operator_supplied_rates": rates,
        "pricing_note": "Apify run charges have a provider-enforced dollar ceiling. Other stages have call/record caps; confirm model rates and existing provider plans. No subscriptions or credits are purchased. Failed requests may be billed; no automatic retries.",
        "llm_limits": {"max_source_characters_per_call": c["checks"]["max_description_chars"], "max_output_tokens_per_call": c["analysis"]["max_output_tokens"]},
        "includes_sending": False,
    }
