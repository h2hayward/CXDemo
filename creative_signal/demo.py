from __future__ import annotations

import json
from importlib.resources import files

from .common import now, write_json
from .http import Transport


def load_fixture():
    return json.loads(files("creative_signal").joinpath("demo.json").read_text(encoding="utf-8"))


class DemoTransport(Transport):
    """Replay provider-shaped fixtures. All normal adapters and qualification gates run."""

    def __init__(self, output, limits, fixture):
        super().__init__(output, limits)
        self.fixture = fixture
        self.apify_domains = {}

    def credential(self, name):
        return "synthetic-demo-placeholder"

    def api(self, provider, url, *, headers=None, body=None, response_type="object"):
        receipt = self.reserve(provider)
        if provider == "jsearch":
            result = {"status": "OK", "data": {"jobs": self.fixture["jobs"] if self.counts[provider] == 1 else []}}
        elif provider == "ads" and "api.apify.com" in url:
            page = body["startUrls"][0]["url"]
            pages = self.fixture["config"]["checks"]["facebook_pages"]
            d = next(d for d, p in pages.items() if p == page)
            run_id = "syntheticRun" + str(self.counts["ads"])
            self.apify_domains[run_id] = d
            result = {"data": {"id": run_id, "status": "SUCCEEDED", "defaultDatasetId": run_id,
                               "usageTotalUsd": 0, "synthetic": True}}
        elif provider == "apify_dataset":
            dataset_id = url.split("/datasets/")[1].split("/")[0]
            d = self.apify_domains[dataset_id]
            from .providers import flatten_rows
            page = self.fixture["config"]["checks"]["facebook_pages"][d]
            rows = []
            for ad in flatten_rows(self.fixture["ads"][d].get("results", [])):
                s = ad.get("snapshot", {})
                rows.append({"adArchiveID": ad.get("ad_archive_id"), "pageID": ad.get("page_id", "123"),
                             "isActive": ad.get("is_active", True), "pageName": s.get("page_name"),
                             "snapshot": {"pageProfileUri": page, "linkUrl": s.get("link_url"),
                                          "cards": [{"linkUrl": c.get("link_url")} for c in s.get("cards", [])]}})
            result = rows if "/items?" in url else {"data": {"itemCount": len(rows)}}
        elif provider == "ads":
            result = self.fixture["ads"][body["company_domain"]]
        elif provider == "llm":
            supplied = json.loads(body["input"])
            value = self.fixture["analyses"][supplied["company"]]
            result = {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(value)}]}]}
        elif provider == "blitz" and url.endswith("domain-to-linkedin"):
            result = {"found": True, "company_linkedin_url": "https://www.linkedin.com/company/synthetic-" + body["domain"].split(".")[0]}
        elif provider == "blitz":
            result = self.fixture["people"][body["company_linkedin_url"]]
        else:
            raise AssertionError("Unrecognized fixture request")
        write_json(self.output / "evidence" / (receipt + ".json"), result)
        write_json(self.output / "receipts" / (receipt + ".json"), {"provider": provider, "state": "fixture_replayed", "synthetic": True, "network_calls": 0, "evidence": "evidence/" + receipt + ".json"})
        return result

    def web(self, url):
        receipt = self.reserve("public_web")
        result = {"url": url, "checked_at": self.fixture["clock"], "http_status": 200,
                  "text": self.fixture["pages"][url], "evidence_file": f"evidence/{receipt}.json", "synthetic": True}
        write_json(self.output / result["evidence_file"], result)
        return result
