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

TRUST_VERSION = 3
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
    "AU": ("australia",),
    "NZ": ("new zealand",),
    "IN": ("india",),
    "DE": ("germany",),
    "FR": ("france",),
    "NL": ("netherlands",),
    "ES": ("spain",),
    "PT": ("portugal",),
    "IE": ("ireland",),
    "BR": ("brazil",),
    "CN": ("china",),
    "CO": ("colombia",),
    "HR": ("croatia",),
    "IT": ("italy",),
    "JP": ("japan",),
    "KR": ("south korea", "korea"),
    "LU": ("luxembourg",),
    "MX": ("mexico",),
    "MY": ("malaysia",),
    "PH": ("philippines",),
    "PL": ("poland",),
    "SE": ("sweden",),
    "SG": ("singapore",),
    "TW": ("taiwan",),
    "UY": ("uruguay",),
}
REGION_TERMS = {
    "NA": ("north america", "amer", "americas"),
    "EU": ("european union", "europe"),
    "APAC": ("apac", "asia pacific"),
    "EMEA": ("emea",),
    "LATAM": ("latam", "latin america"),
    "GCC": ("gcc", "gulf cooperation council"),
}
WORLDWIDE_PATTERNS = (
    re.compile(r"\bworldwide\b", re.I),
    re.compile(r"\banywhere in the world\b", re.I),
    re.compile(r"\bwork from any country\b", re.I),
    re.compile(r"\bglobally remote\b", re.I),
    re.compile(r"\bremote (?:from )?anywhere in the world\b", re.I),
)
DESCRIPTION_WORLDWIDE_PATTERNS = (
    re.compile(r"\bglobally remote\b", re.I),
    re.compile(r"\bwork remotely from anywhere in the world\b", re.I),
    re.compile(r"\bwork from any country\b", re.I),
    re.compile(
        r"\b(?:this|the) (?:role|position|job)\b.{0,50}\b"
        r"(?:worldwide|anywhere in the world|open globally)\b",
        re.I,
    ),
    re.compile(
        r"\bwe (?:can |do )?(?:hire|employ|accept candidates?)\b.{0,60}\b"
        r"(?:worldwide|globally|anywhere in the world|from any country)\b",
        re.I,
    ),
)
PAKISTAN_PATTERNS = (
    re.compile(r"\b(?:open to|hiring|candidates? (?:in|from)|located in) Pakistan\b", re.I),
)
RESTRICTIVE_PATTERNS = (
    re.compile(
        r"\b(?:US|U\.S\.|USA|United States|Canada|UK|United Kingdom|EU|European Union|"
        r"Europe|North America|LATAM|Latin America|APAC|EMEA)[- ]only\b",
        re.I,
    ),
    re.compile(
        r"\b(?:remote|work|working|anywhere)\s+(?:from\s+)?(?:within|in)\s+"
        r"(?:this|these|the)?\s*(?:country|countries|region|regions|US|U\.S\.|USA|"
        r"United States|Canada|UK|United Kingdom|EU|European Union|Europe|North America|"
        r"LATAM|Latin America|APAC|EMEA|GCC)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:role is open to|open to|candidates?|applicants?|you)\b.{0,80}\b"
        r"(?:must|need to|required to|based|located|reside|live)\b.{0,30}\bin\b",
        re.I,
    ),
    re.compile(r"\b(?:must|need to|required to)\s+(?:be\s+)?based\b", re.I),
    re.compile(r"\b(?:authorized|eligible) to work in (?:the )?(?:US|USA|United States)\b", re.I),
    re.compile(r"\b(?:work authorization|right to work)\b.{0,40}\b(?:required|must|need)\b", re.I),
)
EXCLUSION_PATTERNS = (
    re.compile(r"\b(?:worldwide|anywhere).{0,40}\b(?:except|excluding|not available in)\b", re.I),
    re.compile(r"\b(?:except|excluding)\s+(?:candidates?\s+)?(?:in|from)\b", re.I),
)
RESIDENCY_PATTERNS = (
    re.compile(
        r"\b(?:must|required to|need to)\s+(?:be\s+)?(?:resident|reside|live|based)\b",
        re.I,
    ),
    re.compile(r"\b(?:tax|legal) residency\b", re.I),
)
AUTHORIZATION_PATTERNS = (
    re.compile(r"\bwork authorization\b", re.I),
    re.compile(r"\bright to work\b", re.I),
    re.compile(r"\bauthorized to work\b", re.I),
)
TIMEZONE_PATTERNS = (
    re.compile(r"\b(?:UTC|GMT)\s*[+-]\s*\d{1,2}\b", re.I),
    re.compile(r"\b(?:time ?zone|working hours|hours overlap)\b", re.I),
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
    geographic_scope: str
    allowed_country_codes: list[str]
    excluded_country_codes: list[str]
    allowed_regions: list[str]
    residency_required: bool
    work_authorization_required: bool
    timezone_constraints: list[str]
    global_remote: bool
    eligibility_confidence: str
    geographic_positive_evidence: list[str]
    geographic_restrictive_evidence: list[str]
    geographic_conflicting_evidence: list[str]
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
    if "fulltime" in compact or "permanent" in compact:
        return "full-time"
    if "parttime" in compact:
        return "part-time"
    if "contract" in compact or "freelance" in compact:
        return "contract"
    if "temporary" in compact:
        return "temporary"
    if "intern" in compact:
        return "internship"
    return clean_text(value).casefold()[:32]


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
    for code, terms in {**GCC_TERMS, **OTHER_LOCATION_TERMS, **REGION_TERMS}.items():
        if any(re.search(rf"\b{re.escape(term)}\b", text, re.I) for term in terms):
            kind = "region" if code in REGION_TERMS else "country"
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
    location = clean_text(job.location_text).casefold()
    combined = f"{location} {job.description_text}".casefold()
    if "hybrid" in workplace or location == "hybrid" or re.search(
        r"\bhybrid (?:role|work|position)\b", combined
    ):
        return "hybrid"
    if (
        workplace in {"on-site", "onsite", "office"}
        or location in {"in-office", "office", "office based", "onsite", "on-site"}
        or location.startswith("office based")
        or re.search(
        r"\b(?:on-site|onsite) (?:role|work|position)\b", combined
        )
    ):
        return "onsite"
    if "remote" in workplace or "remote" in (job.location_text or "").casefold():
        return "remote"
    if re.search(r"\b(?:fully remote|remote role|work remotely)\b", combined):
        return "remote"
    return "unknown"


def _location_codes(text: str) -> tuple[set[str], set[str]]:
    lowered = text.casefold()
    countries = {
        code
        for code, terms in {**GCC_TERMS, **OTHER_LOCATION_TERMS}.items()
        if any(re.search(rf"\b{re.escape(term)}\b", lowered, re.I) for term in terms)
    }
    regions = {
        code
        for code, terms in REGION_TERMS.items()
        if any(re.search(rf"\b{re.escape(term)}\b", lowered, re.I) for term in terms)
    }
    return countries, regions


def _normalize_source_country(value: str) -> str | None:
    cleaned = clean_text(value).upper()
    aliases = {
        "USA": "US",
        "UNITED STATES": "US",
        "UNITED KINGDOM": "GB",
        "UK": "GB",
        "PAKISTAN": "PK",
        "UAE": "AE",
        "UNITED ARAB EMIRATES": "AE",
    }
    if cleaned in aliases:
        return aliases[cleaned]
    return cleaned if re.fullmatch(r"[A-Z]{2}", cleaned) else None


def _location_is_generic(location: str) -> bool:
    compact = re.sub(r"[^a-z]+", " ", location.casefold()).strip()
    if not compact:
        return True
    return compact in {
        "remote",
        "fully remote",
        "remote work",
        "global",
        "remote global",
        "worldwide",
        "remote worldwide",
        "home based worldwide",
        "anywhere",
        "n a",
    }


def _geographic_eligibility(
    job: NormalizedJob,
    remote_mode: str,
) -> tuple[
    str,
    str,
    list[str],
    list[str],
    list[str],
    bool,
    bool,
    list[str],
    bool,
    str,
    list[str],
    list[str],
    list[str],
]:
    location = clean_text(job.location_text)
    text = f"{location}. {job.description_text}"
    location_worldwide = _evidence(location, WORLDWIDE_PATTERNS)
    if re.search(r"\bglobal\b", location, re.I):
        location_worldwide = list(dict.fromkeys([location, *location_worldwide]))[:5]
    description_worldwide = _evidence(job.description_text, DESCRIPTION_WORLDWIDE_PATTERNS)
    worldwide = list(dict.fromkeys([*location_worldwide, *description_worldwide]))[:5]
    pakistan = _evidence(text, PAKISTAN_PATTERNS)
    restrictive = _evidence(text, RESTRICTIVE_PATTERNS)
    exclusions = _evidence(text, EXCLUSION_PATTERNS)
    residency = bool(_evidence(text, RESIDENCY_PATTERNS))
    authorization = bool(_evidence(text, AUTHORIZATION_PATTERNS))
    timezone_constraints = _evidence(text, TIMEZONE_PATTERNS)

    location_countries, location_regions = _location_codes(location)
    restriction_text = " ".join(restrictive)
    restricted_countries, restricted_regions = _location_codes(restriction_text)
    exclusion_countries, _ = _location_codes(" ".join(exclusions))
    source_countries = {
        code
        for value in job.source_country_codes
        if (code := _normalize_source_country(value)) is not None
    }
    allowed_countries = sorted(location_countries | restricted_countries | source_countries)
    allowed_regions = sorted(location_regions | restricted_regions)
    excluded_countries = sorted(exclusion_countries)
    location_restricted = bool(location) and not _location_is_generic(location)

    positive = list(dict.fromkeys([*worldwide, *pakistan]))[:5]
    if "PK" in location_countries and location and location not in positive:
        positive.insert(0, location)
    negative = list(dict.fromkeys([*restrictive, *exclusions]))[:5]
    if remote_mode in {"hybrid", "onsite"}:
        negative.insert(0, f"Work mode classified as {remote_mode}")

    conflicts: list[str] = []
    global_remote = False
    confidence = "low"
    scope = "unknown"
    eligibility = "unknown"

    if remote_mode in {"hybrid", "onsite"}:
        eligibility = "no"
        confidence = "high"
    elif worldwide and exclusions and not location_restricted:
        scope = "country_list"
        eligibility = "no" if "PK" in exclusion_countries else "yes"
        confidence = "high" if exclusion_countries else "medium"
    elif "PK" in set(allowed_countries) or pakistan:
        scope = "single_country" if allowed_countries == ["PK"] else "country_list"
        eligibility = "yes"
        confidence = "high"
        if worldwide:
            conflicts = list(dict.fromkeys([*worldwide, location]))[:5]
    elif location_countries or restricted_countries or source_countries:
        scope = "single_country" if len(allowed_countries) == 1 else "country_list"
        eligibility = "no"
        confidence = "high"
        if worldwide:
            conflicts = list(dict.fromkeys([*worldwide, *restrictive, location]))[:5]
    elif location_regions or restricted_regions:
        scope = "region"
        if set(allowed_regions) & {"NA", "EU", "LATAM"}:
            eligibility = "no"
            confidence = "high"
        else:
            eligibility = "unknown"
            confidence = "medium"
        if worldwide:
            conflicts = list(dict.fromkeys([*worldwide, *restrictive, location]))[:5]
    elif location_restricted:
        # A provider location such as a city or an unrecognised country is still a
        # geographic restriction. Prefer a safe exclusion over treating a generic
        # use of "worldwide" in company copy as permission to work from anywhere.
        scope = "unknown"
        eligibility = "no"
        confidence = "high"
        if location not in negative:
            negative.insert(0, location)
        if worldwide:
            conflicts = list(dict.fromkeys([*worldwide, location]))[:5]
    elif worldwide:
        if exclusions:
            scope = "country_list"
            eligibility = "no" if "PK" in exclusion_countries else "yes"
            confidence = "high" if exclusion_countries else "medium"
        elif restrictive:
            conflicts = list(dict.fromkeys([*worldwide, *restrictive, location]))[:5]
            scope = "unknown"
            eligibility = "unknown"
            confidence = "low"
        else:
            scope = "worldwide"
            eligibility = "yes"
            global_remote = True
            confidence = "high"
    elif remote_mode == "remote":
        scope = "unknown"
        eligibility = "unknown"

    if (residency or authorization) and eligibility == "yes" and "PK" not in allowed_countries:
        eligibility = "unknown"
        global_remote = False
        confidence = "low"
        conflicts = list(dict.fromkeys([*conflicts, *positive, *negative]))[:5]

    return (
        eligibility,
        scope,
        allowed_countries,
        excluded_countries,
        allowed_regions,
        residency,
        authorization,
        timezone_constraints,
        global_remote,
        confidence,
        positive,
        negative,
        conflicts,
    )


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
    (
        eligibility,
        geographic_scope,
        allowed_country_codes,
        excluded_country_codes,
        allowed_regions,
        residency_required,
        work_authorization_required,
        timezone_constraints,
        global_remote,
        eligibility_confidence,
        positive,
        negative,
        conflicts,
    ) = _geographic_eligibility(job, remote_mode)
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
        geographic_scope=geographic_scope,
        allowed_country_codes=allowed_country_codes,
        excluded_country_codes=excluded_country_codes,
        allowed_regions=allowed_regions,
        residency_required=residency_required,
        work_authorization_required=work_authorization_required,
        timezone_constraints=timezone_constraints,
        global_remote=global_remote,
        eligibility_confidence=eligibility_confidence,
        geographic_positive_evidence=positive,
        geographic_restrictive_evidence=negative,
        geographic_conflicting_evidence=conflicts,
        employer_headquarters_gcc=employer_headquarters_gcc,
        job_location_gcc=job_location_gcc,
        description_fingerprint=description_fingerprint,
        dedupe_key=dedupe_key,
    )
