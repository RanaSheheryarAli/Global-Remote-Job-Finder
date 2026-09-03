from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from app.ingestion.contracts import NormalizedJob

TRUST_VERSION = 1
KARACHI = ZoneInfo("Asia/Karachi")
SAFE_TAGS = {"p", "br", "strong", "em", "b", "i", "ul", "ol", "li", "h2", "h3", "h4", "a"}
DROP_TAGS = {"script", "style", "iframe", "object", "embed", "form"}
SPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9+#.]{2,}")
GCC_TERMS = {
    "BH": ("bahrain", "manama"),
    "KW": ("kuwait", "kuwait city"),
    "OM": ("oman", "muscat"),
    "QA": ("qatar", "doha"),
    "SA": ("saudi arabia", "riyadh", "jeddah", "ksa"),
    "AE": ("united arab emirates", "uae", "dubai", "abu dhabi"),
}
OTHER_LOCATION_TERMS = {
    "PK": ("pakistan", "islamabad", "lahore", "karachi"),
    "US": ("united states", "usa", "u.s."),
    "CA": ("canada",),
    "GB": ("united kingdom", "uk", "great britain"),
    "EU": ("european union", "europe", "eu"),
    "APAC": ("apac", "asia pacific"),
    "EMEA": ("emea",),
}
POSITIVE_PATTERNS = (
    re.compile(r"\bworldwide\b", re.I),
    re.compile(r"\bwork from anywhere\b", re.I),
    re.compile(r"\banywhere in the world\b", re.I),
    re.compile(r"\bglobally remote\b", re.I),
    re.compile(r"\bremote anywhere\b", re.I),
    re.compile(r"\b(?:open to|hiring|candidates? (?:in|from)|located in) Pakistan\b", re.I),
)
NEGATIVE_PATTERNS = (
    re.compile(
        r"\b(?:US|U\.S\.|USA|United States|Canada|UK|United Kingdom|EU|European Union)"
        r"[- ]only\b",
        re.I,
    ),
    re.compile(
        r"\bremote\s+(?:within|in)\s+(?:the\s+)?"
        r"(?:US|U\.S\.|USA|United States|Canada|UK|United Kingdom|EU|European Union)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:candidates?|applicants?|you)\s+(?:must|need to|required to)\s+"
        r"(?:be\s+)?(?:based|located|reside|live)\s+in\b",
        re.I,
    ),
    re.compile(r"\b(?:authorized|eligible) to work in (?:the )?(?:US|USA|United States)\b", re.I),
    re.compile(r"\bUS work authorization required\b", re.I),
)
REGIONAL_PATTERNS = (
    re.compile(r"\bAPAC\b", re.I),
    re.compile(r"\bEMEA\b", re.I),
    re.compile(r"\bGCC\b", re.I),
)
STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "have",
    "job",
    "our",
    "that",
    "the",
    "this",
    "with",
    "you",
}


class SafeHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.drop_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in DROP_TAGS:
            self.drop_depth += 1
            return
        if self.drop_depth or tag not in SAFE_TAGS:
            return
        if tag == "a":
            href = next((value for name, value in attrs if name.lower() == "href"), None)
            if href and urlsplit(href).scheme == "https":
                self.parts.append(f'<a href="{html.escape(href, quote=True)}" rel="noopener">')
                return
            self.parts.append("<a>")
            return
        self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in DROP_TAGS and self.drop_depth:
            self.drop_depth -= 1
            return
        if not self.drop_depth and tag in SAFE_TAGS and tag != "br":
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.drop_depth:
            self.parts.append(html.escape(data))


@dataclass(frozen=True, slots=True)
class TrustClassification:
    normalized_title: str
    normalized_employment_type: str | None
    normalized_compensation: dict[str, Any] | None
    structured_locations: list[dict[str, str]]
    sanitized_description_html: str
    freshness_grade: str
    freshness_label: str
    published_local_date: date | None
    is_reposted: bool
    reposted_at: datetime | None
    remote_mode: str
    pakistan_eligibility: str
    positive_evidence: list[str]
    negative_evidence: list[str]
    employer_headquarters_gcc: bool
    job_location_gcc: bool | None
    description_fingerprint: str
    dedupe_key: str


def clean_text(value: str | None) -> str:
    return SPACE_RE.sub(" ", (value or "").strip())


def normalize_title(value: str) -> str:
    return clean_text(re.sub(r"[^a-z0-9+#.]+", " ", html.unescape(value).casefold()))


def normalize_employment_type(value: str | None) -> str | None:
    compact = re.sub(r"[^a-z]", "", (value or "").casefold())
    if not compact:
        return None
    mappings = {
        "fulltime": "full-time",
        "permanent": "full-time",
        "parttime": "part-time",
        "contract": "contract",
        "contractor": "contract",
        "temporary": "temporary",
        "intern": "internship",
        "internship": "internship",
    }
    return mappings.get(compact, clean_text(value).casefold())


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"(\d+(?:\.\d+)?)\s*([kK])?", value.replace(",", ""))
        if match:
            number = float(match.group(1))
            return number * 1000 if match.group(2) else number
    return None


def normalize_compensation(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    summary = str(value.get("compensationTierSummary") or value.get("summary") or "")
    numbers = [_number(item) for item in re.findall(r"\d[\d,.]*\s*[kK]?", summary)]
    numbers = [item for item in numbers if item is not None]
    minimum = _number(value.get("min") or value.get("minimum"))
    maximum = _number(value.get("max") or value.get("maximum"))
    if minimum is None and numbers:
        minimum = numbers[0]
    if maximum is None and numbers:
        maximum = numbers[-1]
    currency = value.get("currency")
    if not currency and "$" in summary:
        currency = "USD"
    result = {
        "min": minimum,
        "max": maximum,
        "currency": currency,
        "interval": value.get("interval"),
        "summary": summary or None,
    }
    return result if any(item is not None for item in result.values()) else None


def sanitize_html(value: str) -> str:
    parser = SafeHtmlParser()
    parser.feed(value)
    parser.close()
    return "".join(parser.parts)


def _evidence(text: str, patterns: tuple[re.Pattern[str], ...]) -> list[str]:
    snippets: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            start = max(
                text.rfind(".", 0, match.start()) + 1, text.rfind("\n", 0, match.start()) + 1
            )
            stops = [
                index
                for index in (text.find(".", match.end()), text.find("\n", match.end()))
                if index >= 0
            ]
            end = min(stops) + 1 if stops else min(len(text), match.end() + 120)
            snippet = clean_text(text[start:end])[:240]
            if snippet and snippet not in snippets:
                snippets.append(snippet)
    return snippets[:5]


def _structured_locations(location: str | None) -> list[dict[str, str]]:
    text = (location or "").casefold()
    result: list[dict[str, str]] = []
    for code, terms in {**GCC_TERMS, **OTHER_LOCATION_TERMS}.items():
        if any(re.search(rf"\b{re.escape(term)}\b", text, re.I) for term in terms):
            kind = "region" if code in {"EU", "APAC", "EMEA"} else "country"
            result.append({"kind": kind, "code": code})
    if "worldwide" in text or "anywhere" in text:
        result.append({"kind": "scope", "code": "WORLDWIDE"})
    return result


def _freshness(
    source_type: str,
    published_at: datetime | None,
    prior_published_at: datetime | None,
) -> tuple[str, str, date | None, bool, datetime | None]:
    republished = bool(published_at and prior_published_at and published_at > prior_published_at)
    if published_at and source_type in {"greenhouse", "ashby"}:
        grade, label = "A", "Verified publication time"
    elif published_at and source_type == "remoteok":
        grade, label = "B", "Feed-verified publication time"
    elif source_type == "lever":
        grade, label = "C", "Newly discovered; publication time unavailable"
    else:
        grade, label = "D", "Publication time unverified"
    if republished:
        label = f"Republished - {label}"
    local_date = (
        published_at.astimezone(KARACHI).date() if published_at and grade in {"A", "B"} else None
    )
    return grade, label, local_date, republished, published_at if republished else None


def _remote_mode(job: NormalizedJob) -> str:
    workplace = (job.workplace_type or "").casefold()
    combined = f"{job.location_text or ''} {job.description_text}".casefold()
    if "hybrid" in workplace or re.search(r"\bhybrid (?:role|work|position)\b", combined):
        return "hybrid"
    if workplace in {"on-site", "onsite", "office"} or re.search(
        r"\b(?:on-site|onsite) (?:role|work|position)\b", combined
    ):
        return "onsite"
    if "remote" in workplace or "remote" in (job.location_text or "").casefold():
        return "remote"
    if re.search(r"\b(?:fully remote|remote role|work remotely)\b", combined):
        return "remote"
    return "unknown"


def _eligibility(job: NormalizedJob, remote_mode: str) -> tuple[str, list[str], list[str]]:
    text = f"{job.location_text or ''}. {job.description_text}"
    positive = _evidence(text, POSITIVE_PATTERNS)
    if "pakistan" in (job.location_text or "").casefold() and job.location_text not in positive:
        positive.insert(0, clean_text(job.location_text))
    negative = _evidence(text, NEGATIVE_PATTERNS)
    regional = _evidence(text, REGIONAL_PATTERNS)
    if remote_mode in {"hybrid", "onsite"}:
        negative.insert(0, f"Work mode classified as {remote_mode}")
    if positive and negative:
        return "unknown", positive, negative
    if negative:
        return "no", positive, negative
    if positive:
        return "yes", positive, negative
    return "unknown", positive, regional


def description_similarity(left: str, right: str) -> float:
    left_tokens = {token for token in TOKEN_RE.findall(left.casefold()) if token not in STOPWORDS}
    right_tokens = {token for token in TOKEN_RE.findall(right.casefold()) if token not in STOPWORDS}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def is_strict_today(classification: TrustClassification, *, now: datetime) -> bool:
    return (
        classification.freshness_grade in {"A", "B"}
        and classification.published_local_date == now.astimezone(KARACHI).date()
        and classification.remote_mode == "remote"
        and classification.pakistan_eligibility == "yes"
    )


def classify_job(
    job: NormalizedJob,
    *,
    source_type: str,
    employer_headquarters_gcc: bool,
    prior_published_at: datetime | None = None,
) -> TrustClassification:
    normalized_title = normalize_title(job.title)
    locations = _structured_locations(job.location_text)
    grade, label, local_date, reposted, reposted_at = _freshness(
        source_type, job.first_published_at, prior_published_at
    )
    remote_mode = _remote_mode(job)
    eligibility, positive, negative = _eligibility(job, remote_mode)
    gcc_codes = set(GCC_TERMS)
    location_codes = {item["code"] for item in locations}
    if location_codes & gcc_codes:
        job_location_gcc: bool | None = True
    elif locations or remote_mode == "remote":
        job_location_gcc = False
    else:
        job_location_gcc = None
    fingerprint_text = clean_text(job.description_text).casefold()
    description_fingerprint = hashlib.sha256(fingerprint_text.encode()).hexdigest()
    location_key = ",".join(sorted(location_codes)) or clean_text(job.location_text).casefold()
    company_key = clean_text(job.employer_name).casefold()
    dedupe_material = "|".join((company_key, normalized_title, location_key))
    dedupe_key = hashlib.sha256(dedupe_material.encode()).hexdigest()
    return TrustClassification(
        normalized_title=normalized_title,
        normalized_employment_type=normalize_employment_type(job.employment_type),
        normalized_compensation=normalize_compensation(job.compensation),
        structured_locations=locations,
        sanitized_description_html=sanitize_html(job.description_html),
        freshness_grade=grade,
        freshness_label=label,
        published_local_date=local_date,
        is_reposted=reposted,
        reposted_at=reposted_at,
        remote_mode=remote_mode,
        pakistan_eligibility=eligibility,
        positive_evidence=positive,
        negative_evidence=negative,
        employer_headquarters_gcc=employer_headquarters_gcc,
        job_location_gcc=job_location_gcc,
        description_fingerprint=description_fingerprint,
        dedupe_key=dedupe_key,
    )
