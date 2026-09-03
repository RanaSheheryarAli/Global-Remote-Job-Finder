from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from io import BytesIO

from pypdf import PdfReader

from app.matching.ontology import (
    ARCHITECTURE_ALIASES,
    DOMAIN_ALIASES,
    extract_named_traits,
    extract_skills,
)

HEADLINE_RE = re.compile(
    r"\b(?:(?:Senior|Lead|Staff|Principal|Junior)\s+)?"
    r"(?:Full[- ]Stack|Backend|Frontend|Mobile|Software|Platform|Cloud|AI|ML)\s+"
    r"(?:Engineer|Developer|Architect|Lead)\b",
    re.I,
)


@dataclass(frozen=True, slots=True)
class CandidateFacts:
    full_name: str
    headline: str
    location: str | None
    timezone: str
    years_experience: float
    role_families: list[str]
    seniority_levels: list[str]
    skills: dict[str, list[str]]
    cloud_platforms: list[str]
    domains: list[str]
    preferences: dict
    extraction_evidence: dict


@dataclass(frozen=True, slots=True)
class ParsedResume:
    facts: CandidateFacts
    sha256: str


def _role_families(text: str) -> list[str]:
    lowered = text.casefold()
    checks = (
        ("full_stack", ("full stack", "full-stack", "frontend", "react")),
        ("backend", ("backend", "back-end", "node.js", "fastapi", "rest api")),
        ("ai_llm", ("llm", "rag", "langchain", "openai api", "ai-enabled")),
        ("platform_cloud", ("platform", "cloud", "devops", "kubernetes", "terraform")),
        ("mobile", ("mobile", "ios", "android", "react native")),
    )
    return [family for family, terms in checks if any(term in lowered for term in terms)]


def _years_experience(text: str, *, today: date) -> tuple[float, str | None]:
    professional = text
    if "PROFESSIONAL EXPERIENCE" in text:
        professional = text.split("PROFESSIONAL EXPERIENCE", 1)[1]
    if "EDUCATION" in professional:
        professional = professional.split("EDUCATION", 1)[0]
    dates = [
        (int(month), int(year))
        for month, year in re.findall(r"\b(0[1-9]|1[0-2])/(20\d{2})\b", professional)
    ]
    if not dates:
        return 0.0, None
    month, year = min(dates, key=lambda item: (item[1], item[0]))
    months = (today.year - year) * 12 + today.month - month
    return round(max(months, 0) / 12, 1), f"{month:02d}/{year}"


def parse_resume_text(text: str, *, today: date | None = None) -> CandidateFacts:
    today = today or date.today()
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("Resume text is too short to create a candidate profile")
    first_line_role = HEADLINE_RE.search(lines[0])
    if first_line_role and first_line_role.start() > 0:
        full_name = lines[0][: first_line_role.start()].strip()[:200]
        headline = first_line_role.group(0)[:300]
    else:
        full_name = lines[0][:200]
        headline = next(
            (line[:300] for line in lines[1:8] if HEADLINE_RE.search(line)),
            "Software Engineer",
        )
    location = next(
        (city for city in ("Lahore", "Karachi", "Islamabad", "Pakistan") if city in text),
        None,
    )
    years, experience_start = _years_experience(text, today=today)
    skills = extract_skills(text)
    cloud_platforms = skills.get("cloud_devops", [])
    cloud_platforms = [item for item in cloud_platforms if item in {"AWS", "Azure", "GCP"}]
    domains = extract_named_traits(text, DOMAIN_ALIASES)
    architecture = extract_named_traits(text, ARCHITECTURE_ALIASES)
    roles = _role_families(text)
    seniority = [level for level in ("lead", "senior") if re.search(rf"\b{level}\b", text, re.I)]
    preferences = {
        "primary_role_families": [
            family for family in ("full_stack", "backend", "ai_llm") if family in roles
        ],
        "secondary_role_families": [
            family for family in ("platform_cloud", "mobile") if family in roles
        ],
        "target_seniority": ["senior", "lead", "staff"],
        "candidate_country": "PK",
        "remote_preference": "worldwide",
        "gulf_employer_preference": True,
    }
    return CandidateFacts(
        full_name=full_name,
        headline=headline,
        location=location,
        timezone="Asia/Karachi",
        years_experience=years,
        role_families=roles,
        seniority_levels=seniority,
        skills=skills,
        cloud_platforms=cloud_platforms,
        domains=domains,
        preferences=preferences,
        extraction_evidence={
            "experience_start": experience_start,
            "latest_role": headline,
            "skill_count": sum(len(items) for items in skills.values()),
            "architecture": architecture,
        },
    )


def parse_resume_pdf(data: bytes, *, today: date | None = None) -> ParsedResume:
    if not data.startswith(b"%PDF"):
        raise ValueError("Only a valid PDF resume is accepted")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Encrypted resumes are not supported")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The PDF could not be parsed") from exc
    return ParsedResume(
        facts=parse_resume_text(text, today=today),
        sha256=hashlib.sha256(data).hexdigest(),
    )
