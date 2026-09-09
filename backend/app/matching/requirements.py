from __future__ import annotations

import re
from dataclasses import dataclass

from app.matching.ontology import extract_skills, flatten_skills

REQUIRED_HEADING = re.compile(
    r"^(requirements?|qualifications?|what (?:you(?:'|’)ll|you will) bring|"
    r"what we(?:'|’)re looking for|minimum qualifications?|must have)s?\s*:?$",
    re.I,
)
PREFERRED_HEADING = re.compile(
    r"^(preferred qualifications?|nice to have|bonus|desired|should have|"
    r"additional skills?)s?\s*:?$",
    re.I,
)
RESPONSIBILITY_HEADING = re.compile(
    r"^(responsibilities|what (?:you(?:'|’)ll|you will) do|the role|your impact|"
    r"how you(?:'|’)ll contribute|job description)\s*:?$",
    re.I,
)
GENERIC_HEADING = re.compile(r"^[A-Z][A-Za-z /&'’()-]{2,60}:?$")
EXPLICIT_REQUIRED = re.compile(
    r"\b(must|required|minimum|at least|proficien(?:t|cy)|expertise|strong experience|"
    r"hands-on experience)\b",
    re.I,
)
EXPLICIT_PREFERRED = re.compile(r"\b(preferred|nice to have|bonus|ideally|a plus)\b", re.I)
YEARS_RE = re.compile(r"\b(\d{1,2})(?:\s*[-–]\s*\d{1,2})?\+?\s*(?:years?|yrs?)\b", re.I)
INLINE_HEADINGS = re.compile(
    r"\b(requirements?|qualifications?|preferred qualifications?|nice to have|"
    r"additional skills?|responsibilities|what you(?:'|’)ll do|what you will do|"
    r"what we(?:'|’)re looking for|job description)\s*:?",
    re.I,
)

THEME_PATTERNS: dict[str, re.Pattern[str]] = {
    "frontend": re.compile(
        r"\b(front[- ]?end|user interface|ui|react|next\.?js|angular|vue)\b", re.I
    ),
    "backend": re.compile(
        r"\b(back[- ]?end|server[- ]side|api|node\.?js|fastapi|express|nestjs)\b", re.I
    ),
    "architecture": re.compile(
        r"\b(architect|system design|distributed|microservices?|scalab|reliab)\w*\b", re.I
    ),
    "cloud_devops": re.compile(
        r"\b(cloud|aws|azure|gcp|devops|ci/cd|docker|kubernetes|terraform)\b", re.I
    ),
    "ai": re.compile(r"\b(ai|llm|machine learning|rag|langchain|agentic|embeddings?)\b", re.I),
    "mobile": re.compile(r"\b(mobile|ios|android|react native|swift|kotlin)\b", re.I),
    "data": re.compile(r"\b(database|postgres|mysql|mongodb|redis|data model|sql)\b", re.I),
    "leadership": re.compile(
        r"\b(lead|mentor|coach|technical direction|stakeholder|ownership)\w*\b", re.I
    ),
    "delivery": re.compile(
        r"\b(build|develop|implement|deliver|deploy|maintain|test|debug)\w*\b", re.I
    ),
}


@dataclass(frozen=True, slots=True)
class JobRequirements:
    required_skills: set[str]
    preferred_skills: set[str]
    all_skills: set[str]
    critical_skills: set[str]
    responsibility_themes: set[str]
    minimum_years: int | None
    confidence: str


def extract_responsibility_themes(text: str) -> set[str]:
    return {name for name, pattern in THEME_PATTERNS.items() if pattern.search(text)}


def parse_job_requirements(title: str, description: str) -> JobRequirements:
    required_parts: list[str] = []
    preferred_parts: list[str] = []
    responsibility_parts: list[str] = []
    section = "other"

    normalized = description.replace("\r", "\n")
    normalized = INLINE_HEADINGS.sub(lambda match: f"\n{match.group(0).strip()}\n", normalized)
    lines = [" ".join(line.split()) for line in normalized.split("\n") if line.strip()]
    for line in lines:
        heading = line.strip(" :-–—")
        if REQUIRED_HEADING.fullmatch(heading):
            section = "required"
            continue
        if PREFERRED_HEADING.fullmatch(heading):
            section = "preferred"
            continue
        if RESPONSIBILITY_HEADING.fullmatch(heading):
            section = "responsibilities"
            continue
        if GENERIC_HEADING.fullmatch(heading) and len(line.split()) <= 8:
            section = "other"

        if EXPLICIT_PREFERRED.search(line):
            preferred_parts.append(line)
        elif EXPLICIT_REQUIRED.search(line) or section == "required":
            required_parts.append(line)
        elif section == "preferred":
            preferred_parts.append(line)
        elif section == "responsibilities":
            responsibility_parts.append(line)

    title_skills = flatten_skills(extract_skills(title))
    required_skills = flatten_skills(extract_skills("\n".join(required_parts))) | title_skills
    preferred_skills = flatten_skills(extract_skills("\n".join(preferred_parts))) - required_skills
    all_skills = flatten_skills(extract_skills(f"{title}\n{description}"))

    explicit_critical: set[str] = set()
    for line in lines:
        if EXPLICIT_REQUIRED.search(line):
            explicit_critical |= flatten_skills(extract_skills(line))
    critical_skills = title_skills | explicit_critical

    years = [int(value) for part in required_parts for value in YEARS_RE.findall(part)]
    responsibility_text = "\n".join(responsibility_parts) or description
    confidence = "high" if required_parts else "medium" if title_skills else "low"
    return JobRequirements(
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        all_skills=all_skills,
        critical_skills=critical_skills,
        responsibility_themes=extract_responsibility_themes(responsibility_text),
        minimum_years=max(years) if years else None,
        confidence=confidence,
    )
