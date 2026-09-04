from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from app.matching.ontology import (
    ARCHITECTURE_ALIASES,
    DOMAIN_ALIASES,
    extract_named_traits,
    extract_skills,
    flatten_skills,
)
from app.matching.profile import CandidateFacts

MATCHER_VERSION = 2
KARACHI = ZoneInfo("Asia/Karachi")
ENTRY_TERMS = re.compile(r"\b(intern(?:ship)?|junior|entry[- ]level|graduate)\b", re.I)
UNRELATED_TERMS = re.compile(
    r"\b(sales|designer|customer support|recruiter|payroll|driver|vehicle detailer|"
    r"domestic|nurse|account executive|business development|marketing)\b",
    re.I,
)


class MatchableJob(Protocol):
    title: str
    description_text: str
    is_active: bool
    is_canonical: bool
    application_url: str
    remote_mode: str
    pakistan_eligibility: str
    normalized_employment_type: str | None
    freshness_grade: str
    published_local_date: object | None
    employer_headquarters_gcc: bool


@dataclass(frozen=True, slots=True)
class MatchResult:
    hard_gate_passed: bool
    uncertain_gate_passed: bool
    gate_reasons: list[str]
    score: int
    score_label: str
    components: dict[str, int]
    matched_skills: list[str]
    missing_skills: list[str]
    evidence: dict


def candidate_facts_from_record(profile: object) -> CandidateFacts:
    return CandidateFacts(
        full_name=profile.full_name,
        headline=profile.headline,
        location=profile.location,
        timezone=profile.timezone,
        years_experience=profile.years_experience,
        role_families=profile.role_families,
        seniority_levels=profile.seniority_levels,
        skills=profile.skills,
        cloud_platforms=profile.cloud_platforms,
        domains=profile.domains,
        preferences=profile.preferences,
        extraction_evidence=profile.extraction_evidence,
    )


def detect_role_family(title: str) -> str | None:
    lowered = title.casefold()
    checks = (
        ("ai_llm", ("ai engineer", "llm", "machine learning", "artificial intelligence")),
        ("mobile", ("mobile", "ios", "android", "react native")),
        ("platform_cloud", ("platform", "cloud", "devops", "sre", "infrastructure")),
        ("backend", ("backend", "back-end", "api engineer", "server engineer")),
        ("full_stack", ("full stack", "full-stack", "frontend", "front-end", "web engineer")),
    )
    for family, terms in checks:
        if any(term in lowered for term in terms):
            return family
    if re.search(r"\bsoftware (?:developer|engineer)\b|\bproduct engineer\b", lowered):
        return "full_stack"
    return None


def _seniority(title: str) -> str:
    lowered = title.casefold()
    for level in ("principal", "staff", "lead", "senior", "junior", "intern"):
        if re.search(rf"\b{level}\b", lowered):
            return level
    return "unspecified"


def _label(score: int) -> str:
    if score >= 85:
        return "Strong match"
    if score >= 70:
        return "Good match"
    if score >= 55:
        return "Possible match"
    return "Low match"


def score_job(
    job: MatchableJob,
    profile: CandidateFacts,
    *,
    now: datetime,
) -> MatchResult:
    family = detect_role_family(job.title)
    seniority = _seniority(job.title)
    base_blockers: list[str] = []
    if not job.is_active or not job.is_canonical:
        base_blockers.append("Job is not the active canonical posting")
    if not job.application_url:
        base_blockers.append("Application URL is missing")
    if job.remote_mode != "remote":
        base_blockers.append(f"Work mode is {job.remote_mode}, not remote")
    if family is None or family not in profile.role_families or UNRELATED_TERMS.search(job.title):
        base_blockers.append("Role family is outside the candidate profile")
    if ENTRY_TERMS.search(job.title) or job.normalized_employment_type == "internship":
        base_blockers.append("Entry-level and internship roles are excluded")
    if job.pakistan_eligibility == "no":
        base_blockers.append("Pakistan eligibility is explicitly restricted")

    strict_gate = not base_blockers and job.pakistan_eligibility == "yes"
    uncertain_gate = not base_blockers and job.pakistan_eligibility in {"yes", "unknown"}
    gate_reasons = list(base_blockers)
    if not base_blockers and job.pakistan_eligibility == "unknown":
        gate_reasons.append("Pakistan eligibility needs review")
    if not uncertain_gate:
        return MatchResult(
            hard_gate_passed=False,
            uncertain_gate_passed=False,
            gate_reasons=gate_reasons,
            score=0,
            score_label="Excluded",
            components={
                "required_core_skills": 0,
                "role_title": 0,
                "seniority_leadership": 0,
                "architecture_cloud_domain": 0,
                "work_arrangement": 0,
                "freshness": 0,
            },
            matched_skills=[],
            missing_skills=[],
            evidence={"role_family": family, "seniority": seniority},
        )

    job_text = f"{job.title}\n{job.description_text}"
    job_skills = flatten_skills(extract_skills(job_text))
    candidate_skills = flatten_skills(profile.skills)
    matched = sorted(job_skills & candidate_skills)
    missing = sorted(job_skills - candidate_skills)
    skills_score = round(35 * len(matched) / len(job_skills)) if job_skills else 0

    primary = set(profile.preferences.get("primary_role_families", []))
    secondary = set(profile.preferences.get("secondary_role_families", []))
    role_score = 20 if family in primary else 15 if family in secondary else 10
    seniority_score = (
        15 if seniority in {"senior", "lead", "staff"} else 13 if seniority == "principal" else 10
    )

    job_architecture = set(extract_named_traits(job_text, ARCHITECTURE_ALIASES))
    job_domains = set(extract_named_traits(job_text, DOMAIN_ALIASES))
    job_cloud = job_skills & {"AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform"}
    candidate_architecture = set(profile.extraction_evidence.get("architecture", []))
    candidate_context = candidate_architecture | set(profile.domains) | candidate_skills
    job_context = job_architecture | job_domains | job_cloud
    context_matches = job_context & candidate_context
    context_score = round(15 * len(context_matches) / len(job_context)) if job_context else 0

    arrangement_score = 0
    if job.pakistan_eligibility == "yes":
        arrangement_score = 8 + (2 if job.employer_headquarters_gcc else 0)
    elif job.pakistan_eligibility == "unknown":
        arrangement_score = 4

    today = now.astimezone(KARACHI).date()
    if job.freshness_grade == "A" and job.published_local_date == today:
        freshness_score = 5
    elif job.freshness_grade == "B" and job.published_local_date == today:
        freshness_score = 4
    elif job.freshness_grade == "A":
        freshness_score = 3
    elif job.freshness_grade == "B":
        freshness_score = 2
    elif job.freshness_grade == "C":
        freshness_score = 1
    else:
        freshness_score = 0

    components = {
        "required_core_skills": skills_score,
        "role_title": role_score,
        "seniority_leadership": seniority_score,
        "architecture_cloud_domain": context_score,
        "work_arrangement": arrangement_score,
        "freshness": freshness_score,
    }
    total = min(sum(components.values()), 100)
    explanation = (
        f"{family.replace('_', ' ')} role; matched {len(matched)} of {len(job_skills)} "
        f"recognized job skills. Pakistan eligibility is {job.pakistan_eligibility}; "
        f"freshness grade is {job.freshness_grade}."
    )
    return MatchResult(
        hard_gate_passed=strict_gate,
        uncertain_gate_passed=uncertain_gate,
        gate_reasons=gate_reasons,
        score=total,
        score_label=_label(total),
        components=components,
        matched_skills=matched,
        missing_skills=missing,
        evidence={
            "role_family": family,
            "seniority": seniority,
            "context_matches": sorted(context_matches),
            "gulf_preference_applied": bool(
                job.employer_headquarters_gcc and job.pakistan_eligibility == "yes"
            ),
            "explanation": explanation,
        },
    )
