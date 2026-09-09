from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.matching.ontology import (
    ARCHITECTURE_ALIASES,
    DOMAIN_ALIASES,
    extract_named_traits,
    extract_skills,
    flatten_skills,
)
from app.matching.profile import CandidateFacts
from app.matching.requirements import parse_job_requirements

MATCHER_VERSION = 3
APPLY_READY_SCORE = 80
REVIEW_SCORE = 68
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
    if score >= APPLY_READY_SCORE:
        return "Apply ready"
    if score >= REVIEW_SCORE:
        return "Review"
    return "Low match"


def _candidate_themes(profile: CandidateFacts) -> set[str]:
    explicit = set(profile.extraction_evidence.get("responsibility_themes", []))
    role_themes = {
        "full_stack": {"frontend", "backend", "delivery"},
        "backend": {"backend", "architecture", "data", "delivery"},
        "ai_llm": {"ai", "backend", "delivery"},
        "platform_cloud": {"cloud_devops", "architecture", "delivery"},
        "mobile": {"mobile", "delivery"},
    }
    for family in profile.role_families:
        explicit.update(role_themes.get(family, set()))
    if profile.seniority_levels:
        explicit.add("leadership")
    return explicit


def _skill_strength(profile: CandidateFacts, skill: str) -> float:
    strengths = profile.extraction_evidence.get("skill_strengths", {})
    level = strengths.get(skill, "working")
    return {"core": 1.0, "strong": 0.85, "working": 0.6, "familiar": 0.35}.get(level, 0.6)


def score_job(
    job: MatchableJob,
    profile: CandidateFacts,
    *,
    now: datetime,
) -> MatchResult:
    family = detect_role_family(job.title)
    seniority = _seniority(job.title)
    requirements = parse_job_requirements(job.title, job.description_text)
    candidate_skills = flatten_skills(profile.skills)
    effective_required = requirements.required_skills or requirements.all_skills
    matched_required = effective_required & candidate_skills
    missing_required = effective_required - candidate_skills
    matched_critical = requirements.critical_skills & candidate_skills
    title_skills = flatten_skills(extract_skills(job.title))
    missing_title_skills = title_skills - candidate_skills
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
    if title_skills and not title_skills.intersection(candidate_skills):
        base_blockers.append(
            "Resume lacks title-critical skills: " + ", ".join(sorted(missing_title_skills))
        )
    if requirements.critical_skills and not matched_critical:
        base_blockers.append("Resume lacks the explicitly mandatory technology")
    if (
        requirements.confidence != "low"
        and len(effective_required) >= 3
        and len(matched_required) / len(effective_required) < 0.35
    ):
        base_blockers.append("Less than 35% of explicit required skills are present")
    if requirements.minimum_years and profile.years_experience < requirements.minimum_years:
        base_blockers.append(
            f"Role requires {requirements.minimum_years}+ years; resume shows "
            f"{profile.years_experience:g}"
        )

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
                "required_skills": 0,
                "responsibilities": 0,
                "role_title": 0,
                "skill_depth": 0,
                "seniority": 0,
                "domain_architecture": 0,
            },
            matched_skills=[],
            missing_skills=[],
            evidence={"role_family": family, "seniority": seniority},
        )

    job_text = f"{job.title}\n{job.description_text}"
    job_skills = requirements.all_skills
    matched = sorted(job_skills & candidate_skills)
    missing = sorted(missing_required)
    required_score = (
        round(
            30
            * sum(_skill_strength(profile, skill) for skill in matched_required)
            / len(effective_required)
        )
        if effective_required
        else 8
    )

    primary = set(profile.preferences.get("primary_role_families", []))
    secondary = set(profile.preferences.get("secondary_role_families", []))
    role_score = 15 if family in primary else 10 if family in secondary else 6
    target_seniority = set(
        profile.preferences.get("target_seniority")
        or profile.seniority_levels
        or ["senior", "lead", "staff"]
    )
    if seniority in target_seniority:
        seniority_score = 10
    elif seniority == "principal":
        seniority_score = 7
    elif seniority == "unspecified":
        seniority_score = 5
    else:
        seniority_score = 3

    candidate_themes = _candidate_themes(profile)
    theme_matches = requirements.responsibility_themes & candidate_themes
    responsibility_score = (
        round(25 * len(theme_matches) / len(requirements.responsibility_themes))
        if requirements.responsibility_themes
        else 8
    )

    depth_skills = matched_required or set(matched)
    depth_score = (
        round(
            15 * sum(_skill_strength(profile, skill) for skill in depth_skills) / len(depth_skills)
        )
        if depth_skills
        else 0
    )

    job_architecture = set(extract_named_traits(job_text, ARCHITECTURE_ALIASES))
    job_domains = set(extract_named_traits(job_text, DOMAIN_ALIASES))
    job_cloud = job_skills & {"AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform"}
    candidate_architecture = set(profile.extraction_evidence.get("architecture", []))
    candidate_context = candidate_architecture | set(profile.domains) | candidate_skills
    job_context = job_architecture | job_domains | job_cloud
    context_matches = job_context & candidate_context
    context_score = round(5 * len(context_matches) / len(job_context)) if job_context else 0

    components = {
        "required_skills": required_score,
        "responsibilities": responsibility_score,
        "role_title": role_score,
        "skill_depth": depth_score,
        "seniority": seniority_score,
        "domain_architecture": context_score,
    }
    total = min(sum(components.values()), 100)
    explanation = (
        f"{family.replace('_', ' ')} role; matched {len(matched_required)} of "
        f"{len(effective_required)} required or inferred skills and "
        f"{len(theme_matches)} of {len(requirements.responsibility_themes)} responsibility themes. "
        f"Pakistan eligibility is {job.pakistan_eligibility}."
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
            "requirements_confidence": requirements.confidence,
            "required_skills": sorted(effective_required),
            "preferred_skills": sorted(requirements.preferred_skills),
            "critical_skills": sorted(requirements.critical_skills),
            "responsibility_themes": sorted(requirements.responsibility_themes),
            "responsibility_matches": sorted(theme_matches),
            "minimum_years": requirements.minimum_years,
            "gulf_preference_applied": bool(
                job.employer_headquarters_gcc and job.pakistan_eligibility == "yes"
            ),
            "explanation": explanation,
        },
    )
