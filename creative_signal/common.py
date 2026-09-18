from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normal(text: str) -> str:
    return " ".join(str(text).split())


def domain(value: str) -> str:
    parsed = urlparse(value if "://" in value else "https://" + value)
    return (parsed.hostname or "").lower().removeprefix("www.").rstrip(".")


def same_domain(url: str, expected: str) -> bool:
    host = domain(url)
    target = domain(expected)
    return bool(target and host and (host == target or host.endswith("." + target)))


def canonical_url(url: str) -> str:
    p = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.startswith("utm_") and k not in {"ref", "source"}]
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", urlencode(query), ""))


def valid_web_url(url: str, resolve: bool = False) -> str:
    if not isinstance(url, str) or "\\" in url or any(ord(c) < 32 for c in url):
        raise ValueError("Malformed public URL")
    p = urlparse(url)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise ValueError("Expected a public HTTP(S) URL without credentials")
    if p.port not in {None, 80, 443}:
        raise ValueError("Unexpected URL port")
    host = p.hostname.lower().rstrip(".")
    if host == "localhost" or "." not in host or host.endswith((".local", ".internal")):
        raise ValueError("Local network URLs are not allowed")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        addresses = []
        if resolve:
            addresses = [ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(host, p.port or 443, type=socket.SOCK_STREAM)]
    if any(not ip.is_global for ip in addresses):
        raise ValueError("Private or reserved network URLs are not allowed")
    return url


def stable_id(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if sep and re.fullmatch(r"[A-Z][A-Z0-9_]*", key.strip()):
            value = value.strip()
            if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key.strip(), value)


def parse_date(value: str | None):
    if not value:
        return None
    try:
        text = str(value)
        # Some employer JobPosting records omit leading month/day zeroes.
        # Accept only an unambiguous year-first date, never guess locale order.
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", text):
            year, month, day = map(int, text.split("-"))
            text = f"{year:04d}-{month:02d}-{day:02d}"
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
    except ValueError:
        return None


def public_company_domain(value: str) -> str:
    d = domain(value)
    blocked = {"linkedin.com", "indeed.com", "glassdoor.com", "google.com", "ziprecruiter.com", "myworkdayjobs.com", "greenhouse.io", "lever.co", "facebook.com"}
    if not d or "." not in d or any(d == x or d.endswith("." + x) for x in blocked):
        return ""
    try:
        valid_web_url("https://" + d)
    except ValueError:
        return ""
    return d
