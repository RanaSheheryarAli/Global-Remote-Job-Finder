from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

TAG_RE = re.compile(r"<[^>]+>")


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def html_to_text(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = TAG_RE.sub(" ", unescaped)
    return " ".join(html.unescape(without_tags).split())


def stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def require_https_url(value: str, *, allowed_hosts: set[str] | None = None) -> str:
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not hostname:
        raise ValueError(f"Expected a valid HTTPS URL, received: {value!r}")
    if allowed_hosts is not None and hostname not in allowed_hosts:
        raise ValueError(f"Unexpected URL host {hostname!r}")
    return value
