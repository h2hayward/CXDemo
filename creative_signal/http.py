from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .common import now, valid_web_url, write_json


class RunHalted(RuntimeError):
    """Stop paid work after an uncertain request or exhausted budget."""


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        valid_web_url(newurl, resolve=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RunHalted("API redirect refused; credentials were not forwarded")


class Transport:
    def __init__(self, output: Path, limits: dict):
        self.output, self.limits = output, limits
        self.counts = {k: 0 for k in limits}
        self.secrets = [v for k, v in os.environ.items() if (k.endswith(("API_KEY", "TOKEN")) or k == "ADYNTEL_EMAIL") and v]

    def redact(self, value):
        if isinstance(value, dict):
            return {k: self.redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.redact(v) for v in value]
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "[REDACTED]")
        return value

    def credential(self, name):
        return os.environ[name]

    def reserve(self, provider: str) -> str:
        if self.counts[provider] >= self.limits[provider]:
            raise RunHalted(f"{provider} request cap reached")
        self.counts[provider] += 1
        return f"{provider}-{self.counts[provider]:04d}"

    def api(self, provider: str, url: str, *, headers=None, body=None, response_type="object"):
        receipt = self.reserve(provider)
        path = self.output / "receipts" / (receipt + ".json")
        write_json(path, {"provider": provider, "started_at": now(), "state": "started", "note": "No request credentials are recorded"})
        request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                         headers={"User-Agent": "CreativeSignalWorkflow/0.1", "Accept": "application/json", "Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
                raw = response.read(8_000_001)
                if len(raw) > 8_000_000:
                    raise ValueError("Response exceeded 8 MB limit")
                result = {"_http_status": 204} if response.status == 204 else json.loads(raw)
                expected = list if response_type == "list" else dict
                if not isinstance(result, expected):
                    raise ValueError("Unexpected response type")
            write_json(self.output / "evidence" / (receipt + ".json"), self.redact(result))
            write_json(path, {"provider": provider, "finished_at": now(), "state": "received", "evidence": f"evidence/{receipt}.json"})
            return self.redact(result)
        except Exception as exc:
            # A timeout may still be billable. Do not replay requests automatically.
            detail = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
            write_json(path, {"provider": provider, "finished_at": now(), "state": "uncertain", "error": detail})
            raise RunHalted(f"{provider}: {detail}; stopped without retry. Inspect {path.name} before rerunning.") from None

    def web(self, url: str) -> dict:
        receipt = self.reserve("public_web")
        result = {"url": url, "checked_at": now(), "text": "", "http_status": None}
        try:
            valid_web_url(url, resolve=True)
            request = urllib.request.Request(url, headers={"User-Agent": "CreativeSignalWorkflow/0.1 (public research)", "Accept": "text/html,application/json"})
            with urllib.request.build_opener(SafeRedirect()).open(request, timeout=20) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError("Page exceeded 2 MB limit")
                result.update(url=response.url, http_status=response.status, text=raw.decode("utf-8", errors="replace"))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            result["error"] = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
        result["evidence_file"] = f"evidence/{receipt}.json"
        result = self.redact(result)
        write_json(self.output / result["evidence_file"], result)
        return result
