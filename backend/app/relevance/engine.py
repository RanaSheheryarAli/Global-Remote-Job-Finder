from __future__ import annotations

import re
from dataclasses import dataclass

RELEVANCE_VERSION = 1

TECHNICAL_TITLE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("full_stack", re.compile(r"\bfull[- ]?stack\b", re.I)),
    ("frontend", re.compile(r"\b(front[- ]?end|react|next\.?js|angular|vue)\b", re.I)),
    (
        "backend",
        re.compile(
            r"\b(back[- ]?end|node\.?js|python|java|php|api)\b.*\b(engineer|developer)\b|"
            r"\b(engineer|developer)\b.*\b(back[- ]?end|node\.?js|python|java|php|api)\b",
            re.I,
        ),
    ),
    (
        "software",
        re.compile(
            r"\bsoftware (engineer|developer|architect)\b|\bproduct engineer\b|"
            r"\bmember of technical staff\b",
            re.I,
        ),
    ),
    ("web", re.compile(r"\bweb (engineer|developer)\b", re.I)),
    (
        "mobile",
        re.compile(
            r"\b(mobile|ios|android|react native) (engineer|developer|lead|architect)\b", re.I
        ),
    ),
    (
        "ai_ml",
        re.compile(
            r"\b(ai|ml|llm|machine learning|artificial intelligence) "
            r"(engineer|developer|architect)\b|\bdata engineer\b",
            re.I,
        ),
    ),
    (
        "platform_cloud",
        re.compile(
            r"\b(platform|cloud|devops|site reliability|sre|infrastructure) "
            r"(engineer|developer|architect)\b",
            re.I,
        ),
    ),
    (
        "quality",
        re.compile(
            r"\b(qa automation|test automation|software development engineer in test|sdet)\b", re.I
        ),
    ),
    ("architecture", re.compile(r"\b(solution|solutions|software|technical) architect\b", re.I)),
)

NON_TECHNICAL_TITLE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "sales",
        re.compile(r"\b(account executive|territory|sales|business development|revenue)\b", re.I),
    ),
    (
        "operations",
        re.compile(
            r"\b(office operations|operations associate|operations coordinator|"
            r"administrative|office manager)\b",
            re.I,
        ),
    ),
    (
        "people",
        re.compile(
            r"\b(recruiter|recruiting|talent acquisition|human resources|hr|"
            r"people partner)\b",
            re.I,
        ),
    ),
    (
        "marketing",
        re.compile(
            r"\b(marketing|content writer|copywriter|social media|communications manager)\b", re.I
        ),
    ),
    (
        "support",
        re.compile(r"\b(customer support|customer success|customer service|call center)\b", re.I),
    ),
    (
        "finance_legal",
        re.compile(
            r"\b(accountant|accounting|payroll|finance analyst|financial controller|"
            r"legal|counsel|paralegal)\b",
            re.I,
        ),
    ),
    (
        "product_design",
        re.compile(
            r"\b(product manager|project manager|program manager|product designer|"
            r"ux designer|ui designer|graphic designer)\b",
            re.I,
        ),
    ),
    (
        "field_work",
        re.compile(r"\b(driver|warehouse|nurse|physician|vehicle detailer|technician)\b", re.I),
    ),
)

TECHNOLOGY_TERMS = re.compile(
    r"\b(react|typescript|javascript|node\.?js|express|nestjs|next\.?js|python|fastapi|"
    r"java|spring|php|laravel|swift|kotlin|objective-c|rest api|graphql|postgresql|mysql|"
    r"mongodb|redis|aws|azure|gcp|docker|kubernetes|terraform|ci/cd|microservices|"
    r"machine learning|llm|rag|langchain|git)\b",
    re.I,
)
ENGINEERING_ACTIONS = re.compile(
    r"\b(build|develop|implement|code|program|architect|design|debug|deploy|test|maintain|"
    r"software development|code review|technical design)\w*\b",
    re.I,
)


@dataclass(frozen=True, slots=True)
class RelevanceDecision:
    accepted: bool | None
    confidence: str
    role_family: str | None
    reason: str
    matched_terms: tuple[str, ...] = ()

    @property
    def needs_detail(self) -> bool:
        return self.accepted is None


def _matches(text: str, patterns: tuple[tuple[str, re.Pattern[str]], ...]) -> list[str]:
    return [name for name, pattern in patterns if pattern.search(text)]


def classify_job_relevance(title: str, description: str | None = None) -> RelevanceDecision:
    normalized_title = " ".join(title.split())
    technical = _matches(normalized_title, TECHNICAL_TITLE_PATTERNS)
    non_technical = _matches(normalized_title, NON_TECHNICAL_TITLE_PATTERNS)

    if technical and not non_technical:
        return RelevanceDecision(
            True,
            "high",
            technical[0],
            "Technical role title matched the supported engineering taxonomy",
            tuple(technical),
        )
    if non_technical and not technical:
        return RelevanceDecision(
            False,
            "high",
            None,
            f"Non-technical role title matched: {', '.join(non_technical)}",
            tuple(non_technical),
        )
    if description is None:
        reason = "Title has conflicting signals" if technical else "Title needs description review"
        return RelevanceDecision(None, "low", technical[0] if technical else None, reason)

    technology_terms = sorted({match.casefold() for match in TECHNOLOGY_TERMS.findall(description)})
    action_count = len(ENGINEERING_ACTIONS.findall(description))
    if len(technology_terms) >= 2 and action_count >= 2 and not non_technical:
        return RelevanceDecision(
            True,
            "medium",
            technical[0] if technical else "software",
            "Description contains sufficient software-engineering evidence",
            tuple(technology_terms[:12]),
        )
    if technical and len(technology_terms) >= 2 and action_count >= 1:
        return RelevanceDecision(
            True,
            "medium",
            technical[0],
            "Technical title was confirmed by the job description",
            tuple([*technical, *technology_terms[:10]]),
        )
    return RelevanceDecision(
        False,
        "medium" if non_technical else "low",
        None,
        "Job does not contain enough software-engineering evidence",
        tuple([*non_technical, *technology_terms[:10]]),
    )
