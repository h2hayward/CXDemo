from __future__ import annotations

import os
from urllib.parse import urlencode

from .common import canonical_url, domain, normal, now, public_company_domain, same_domain, valid_web_url
from .http import RunHalted


REQUIRED_ENV = ["JSEARCH_API_KEY", "ADYNTEL_API_KEY", "ADYNTEL_EMAIL", "BLITZ_API_KEY", "OPENAI_API_KEY", "OPENAI_MODEL"]


def required_keys(config=None):
    if not config:
        return REQUIRED_ENV
    ads = ["APIFY_TOKEN"] if config["checks"].get("ad_provider") == "apify" else ["ADYNTEL_API_KEY", "ADYNTEL_EMAIL"]
    model = ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_MODEL"] if config["analysis"].get("provider") == "azure" else ["OPENAI_API_KEY", "OPENAI_MODEL"]
    return ["JSEARCH_API_KEY", *ads, "BLITZ_API_KEY", *model]


def missing_keys(config=None) -> list[str]:
    return [key for key in required_keys(config) if not os.environ.get(key, "").strip()]


def jsearch(transport, query: str, country: str, date_posted: str, cursor=None) -> dict:
    params = {"query": query, "country": country, "date_posted": date_posted, "num_pages": 1}
    if cursor:
        params["cursor"] = cursor
    data = transport.api("jsearch", "https://api.openwebninja.com/jsearch/search-v2?" + urlencode(params), headers={"x-api-key": transport.credential("JSEARCH_API_KEY")})
    if data.get("status") != "OK" or not isinstance(data.get("data", {}).get("jobs"), list):
        raise RunHalted("JSearch returned an unexpected schema; inspect the receipt")
    return data["data"]


def normalize_job(raw: dict) -> dict:
    links = []
    for option in raw.get("apply_options") or []:
        url = option.get("apply_link")
        if url and option.get("is_direct") is True:
            links.append(url)
    if raw.get("job_apply_link"):
        links.append(raw["job_apply_link"])
    return {"id": str(raw.get("job_id") or ""), "company": str(raw.get("employer_name") or ""),
            "domain": public_company_domain(str(raw.get("employer_website") or "")),
            "title": str(raw.get("job_title") or ""), "description": str(raw.get("job_description") or ""),
            "country": str(raw.get("job_country") or "").upper(), "location": str(raw.get("job_location") or raw.get("job_city") or ""),
            "posted_at": raw.get("job_posted_at_datetime_utc"), "apply_urls": list(dict.fromkeys(links)),
            "listing_url": raw.get("job_apply_link") or raw.get("job_google_link") or "",
            "discovery_url": raw.get("job_google_link") or raw.get("job_apply_link") or "", "source": "JSearch"}


def meta_ads(transport, account_domain: str, country: str, checks=None, aliases=(), company_name=None) -> dict:
    if checks and checks.get("ad_provider") == "apify":
        from .apify_ads import fetch_ads
        return fetch_ads(transport, account_domain, country, checks, aliases, company_name=company_name)
    return transport.api("ads", "https://api.adyntel.com/facebook", body={
        "api_key": transport.credential("ADYNTEL_API_KEY"), "email": transport.credential("ADYNTEL_EMAIL"),
        "company_domain": account_domain, "country_code": country,
        # The documented default is active ads. Never use all_ads or webhooks in this MVP.
    })


def flatten_rows(value):
    if isinstance(value, dict):
        yield value
    elif isinstance(value, list):
        for child in value:
            yield from flatten_rows(child)


def normalize_ads(data: dict, account_domain: str, aliases=(), scope="ALL") -> dict:
    result = {"platform": "Meta", "scope": scope, "checked_at": data.get("_checked_at") or now(), "status": "unknown",
              "provider_reported_count": None, "returned_unique_active_ads": 0,
              "matched_active_ads": 0, "complete": False, "examples": [], "reason": "No usable response"}
    result.update(access_provider=data.get("_access_provider", "Adyntel"),
                  evidence_files=data.get("_evidence_files", []),
                  identity=data.get("_identity"), sample_limit=data.get("_sample_limit"),
                  run_id=data.get("_run_id"), raw_dataset_rows=data.get("_raw_dataset_rows"),
                  dataset_metadata_count=data.get("_dataset_metadata_count"),
                  dataset_metadata_lagged=data.get("_dataset_metadata_lagged", False),
                  page_matched_rows=data.get("_page_matched_rows"),
                  usage_total_usd_preliminary=data.get("_usage_total_usd_preliminary"))
    if data.get("_primary_evidence"):
        result["evidence_file"] = data["_primary_evidence"]
    if data.get("_http_status") == 204:
        result["reason"] = "Adyntel returned 204: domain/page resolution or retrieval may have failed; this is not zero ads"
        return result
    if not isinstance(data.get("results"), list):
        result["reason"] = "Missing ad records; inspect the response"
        return result
    if data.get("country_code") and data["country_code"].upper() != scope.upper():
        result["reason"] = "Returned ad geography differs from the requested scope"
        return result
    count = data.get("number_of_ads")
    result["provider_reported_count"] = count if type(count) is int and count >= 0 else None
    result["complete"] = data.get("is_result_complete") is True and not data.get("continuation_token")
    seen, matched = set(), []
    for ad in flatten_rows(data["results"]):
        ad_id = str(ad.get("ad_archive_id") or "")
        active = ad.get("is_active") if "is_active" in ad else data.get("active_status") == "active"
        if not ad_id or not ad_id.isdigit() or ad_id in seen or active is not True:
            continue
        seen.add(ad_id)
        if ad.get("_page_identity_matches") is False:
            continue
        snapshot = ad.get("snapshot") or {}
        urls = [snapshot.get("link_url") or ""] + [card.get("link_url") or "" for card in snapshot.get("cards") or [] if isinstance(card, dict)]
        landing = next((u for u in urls if any(same_domain(u, d) for d in [account_domain, *aliases]) and u.startswith(("http://", "https://"))), None)
        if landing:
            matched.append({"ad_id": ad_id, "page_name": snapshot.get("page_name") or "", "page_id": str(ad.get("page_id") or data.get("page_id") or ""),
                            "landing_url": landing, "source_url": "https://www.facebook.com/ads/library/?id=" + ad_id})
    result.update(returned_unique_active_ads=len(seen), matched_active_ads=len(matched), examples=matched[:3])
    if matched:
        result.update(status="observed_active", reason="Active records link to the account domain or an explicitly configured alias; native library review remains available")
    elif not data["results"] and count == 0:
        result.update(status="none_observed", reason=data.get("_reason") or "No ads returned in this lookup; other pages, markets and platforms may still advertise")
    else:
        result["reason"] = data.get("_reason") or "Ads could not be tied to the account domain with an active record"
    return result


def find_people(transport, account_domain: str, country: str, max_results: int) -> dict:
    headers = {"x-api-key": transport.credential("BLITZ_API_KEY")}
    resolution = transport.api("blitz", "https://api.blitz-api.ai/v2/enrichment/domain-to-linkedin", headers=headers, body={"domain": account_domain})
    if type(resolution.get("found")) is not bool:
        raise RunHalted("Blitz returned an unexpected company resolution schema")
    if resolution.get("found") is not True:
        return {"results": [], "reason": "Company LinkedIn identity unresolved"}
    company_url = resolution.get("company_linkedin_url") or ""
    if not same_domain(company_url, "linkedin.com") or "/company/" not in company_url:
        raise RunHalted("Blitz returned an invalid company URL")
    # Geography is scoped to the vacancy, never silently restricted to the US.
    data = transport.api("blitz", "https://api.blitz-api.ai/v2/search/employee-finder", headers=headers, body={
        "company_linkedin_url": company_url, "country_code": [country] if len(country) == 2 else ["WORLD"],
        "job_level": ["C-Team", "VP", "Director", "Manager"],
        "job_function": ["Advertising & Marketing", "Art, Culture and Creative Professionals"],
        "max_results": max_results, "page": 1, "min_connections_count": 0,
    })
    if not isinstance(data.get("results"), list):
        raise RunHalted("Blitz returned an unexpected employee schema")
    return {**data, "company_linkedin_url": company_url}


def normalize_people(data: dict, account_domain: str, aliases=(), country="", top=3, signal="", reporting_line="") -> dict:
    candidates, seen = [], set()
    for person in data.get("results", []):
        name = normal(person.get("full_name") or " ".join([person.get("first_name") or "", person.get("last_name") or ""]))
        profile = person.get("linkedin_url") or ""
        if not name or not same_domain(profile, "linkedin.com") or "/in/" not in profile:
            continue
        profile = canonical_url(profile)
        if profile in seen:
            continue
        for experience in person.get("experiences") or []:
            if experience.get("job_is_current") is not True or experience.get("job_end_date"):
                continue
            if not any(same_domain(experience.get("company_domain") or "", d) for d in [account_domain, *aliases]):
                continue
            title = normal(experience.get("job_title") or "")
            lowered = title.lower()
            words = [w for w in ["creative", "content", "brand", "media", "marketing", "insight", "measurement", "effectiveness"] if w in lowered]
            if not words:
                continue
            location = experience.get("job_location") or person.get("location") or {}
            location_country = location.get("country_code") or (person.get("location") or {}).get("country_code") or ""
            score = sum(3 if w in {"creative", "content", "measurement", "effectiveness"} else 1 for w in words)
            score += 2 if country and location_country == country else 0
            score += 1 if any(w in lowered for w in ["director", "head", "vp", "chief"]) else 0
            if signal == "creative_measurement" and any(w in lowered for w in ["measurement", "effectiveness", "insight"]):
                score += 6
            if signal == "creative_governance":
                if "creative" in lowered and any(w in lowered for w in ["operations", "production"]):
                    score += 10
                elif "brand" in lowered:
                    score += 6
            if lowered and lowered in reporting_line.lower():
                score += 3
            candidates.append({"name": name, "title": title, "profile_url": profile, "country": location_country,
                               "evidence_status": "provider_reports_current_role", "relationship": "possible functional owner; reporting line not confirmed",
                               "match_reason": "Current company-domain match; relevant title terms: " + ", ".join(words), "score": score})
            seen.add(profile)
            break
    candidates.sort(key=lambda p: (-p["score"], p["name"]))
    return {"candidates": candidates[:top], "candidates_considered": len(candidates),
            "coverage_complete": data.get("total_pages") == 1,
            "reason": data.get("reason") or "One bounded page; current employment is provider-reported and should be checked before contact"}
