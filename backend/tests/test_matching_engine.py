from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.matching.engine import score_job
from app.matching.profile import CandidateFacts, parse_resume_pdf, parse_resume_text


def candidate() -> CandidateFacts:
    return CandidateFacts(
        full_name="Sample Candidate",
        headline="Senior Full Stack Engineer",
        location="Karachi",
        timezone="Asia/Karachi",
        years_experience=15.4,
        role_families=["full_stack", "backend", "ai_llm", "platform_cloud", "mobile"],
        seniority_levels=["lead", "senior"],
        skills={
            "languages": ["TypeScript", "Python"],
            "backend": ["Node.js", "FastAPI"],
            "data": ["PostgreSQL", "Redis"],
            "cloud_devops": ["AWS", "Docker", "Kubernetes"],
            "ai": ["LLM", "RAG"],
        },
        cloud_platforms=["AWS"],
        domains=["healthcare"],
        preferences={
            "primary_role_families": ["full_stack", "backend", "ai_llm"],
            "secondary_role_families": ["platform_cloud", "mobile"],
        },
        extraction_evidence={
            "architecture": ["distributed_systems", "microservices", "system_design"]
        },
    )


def job(**overrides) -> SimpleNamespace:
    values = {
        "title": "Senior Backend Engineer",
        "description_text": (
            "Build distributed systems and microservices with Node.js, Python, FastAPI, "
            "PostgreSQL, Redis, AWS, Docker and Kubernetes."
        ),
        "is_active": True,
        "is_canonical": True,
        "application_url": "https://example.com/apply",
        "remote_mode": "remote",
        "pakistan_eligibility": "yes",
        "normalized_employment_type": "full-time",
        "freshness_grade": "A",
        "published_local_date": date(2026, 9, 4),
        "employer_headquarters_gcc": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_known_good_score_is_stable_and_explainable() -> None:
    result = score_job(
        job(),
        candidate(),
        now=datetime(2026, 9, 4, 8, tzinfo=UTC),
    )
    assert result.hard_gate_passed is True
    assert result.score == 82
    assert result.score_label == "Apply ready"
    assert result.components == {
        "required_skills": 18,
        "responsibilities": 25,
        "role_title": 15,
        "skill_depth": 9,
        "seniority": 10,
        "domain_architecture": 5,
    }
    assert "Node.js" in result.matched_skills
    assert result.missing_skills == []


def test_unknown_eligibility_requires_opt_in() -> None:
    result = score_job(
        job(pakistan_eligibility="unknown"),
        candidate(),
        now=datetime(2026, 9, 4, 8, tzinfo=UTC),
    )
    assert result.hard_gate_passed is False
    assert result.uncertain_gate_passed is True
    assert result.score == 82
    assert result.gate_reasons == ["Pakistan eligibility needs review"]


def test_ineligible_job_cannot_receive_a_visible_strong_score() -> None:
    result = score_job(
        job(pakistan_eligibility="no"),
        candidate(),
        now=datetime(2026, 9, 4, 8, tzinfo=UTC),
    )
    assert result.hard_gate_passed is False
    assert result.uncertain_gate_passed is False
    assert result.score == 0
    assert result.score_label == "Excluded"


def test_unrelated_and_entry_level_roles_are_excluded() -> None:
    unrelated = score_job(
        job(title="Senior Sales Manager"),
        candidate(),
        now=datetime(2026, 9, 4, tzinfo=UTC),
    )
    entry = score_job(
        job(title="Junior Backend Engineer"),
        candidate(),
        now=datetime(2026, 9, 4, tzinfo=UTC),
    )
    assert unrelated.score == 0 and not unrelated.uncertain_gate_passed
    assert entry.score == 0 and not entry.uncertain_gate_passed


def test_title_technology_and_experience_are_hard_requirements() -> None:
    technology = score_job(
        job(
            title="Senior Java Backend Engineer",
            description_text="Build backend services. Requirements: Java and Spring Boot.",
        ),
        candidate(),
        now=datetime(2026, 9, 4, tzinfo=UTC),
    )
    experience = score_job(
        job(description_text="Requirements: 20+ years of experience with Node.js and Python."),
        candidate(),
        now=datetime(2026, 9, 4, tzinfo=UTC),
    )

    assert technology.score == 0
    assert "Resume lacks title-critical skills: Java" in technology.gate_reasons
    assert experience.score == 0
    assert "Role requires 20+ years; resume shows 15.4" in experience.gate_reasons


def test_resume_text_creates_reviewable_private_facts() -> None:
    text = """Sample Candidate Senior Full Stack Engineer
candidate@example.com +1 555 0100 Karachi
PROFILE
Lead developer using TypeScript, Node.js, React, Python, FastAPI, PostgreSQL and AWS.
Worked with Docker, Kubernetes, LLM, RAG, LangChain and healthcare systems.
PROFESSIONAL EXPERIENCE
Lead Full Stack Engineer 07/2018
Software Engineer 04/2011 - 03/2017
EDUCATION
Bachelor of Science 09/2007 - 06/2011
"""
    facts = parse_resume_text(text, today=date(2026, 9, 4))
    assert facts.full_name == "Sample Candidate"
    assert facts.headline == "Senior Full Stack Engineer"
    assert facts.years_experience == 15.4
    assert facts.extraction_evidence["experience_start"] == "04/2011"
    assert facts.preferences["candidate_country"] == "PK"
    assert facts.preferences["primary_role_families"] == ["full_stack", "backend"]
    assert facts.preferences["secondary_role_families"] == ["ai_llm"]
    assert facts.role_families == ["full_stack", "backend", "ai_llm"]
    assert "Node.js" in facts.skills["backend"]
    assert "ai_llm" in facts.role_families
    assert facts.extraction_evidence["skill_strengths"]["Node.js"] in {"strong", "core"}
    assert not hasattr(facts, "email")


def test_resume_parser_rejects_non_pdf_content() -> None:
    with pytest.raises(ValueError, match="valid PDF"):
        parse_resume_pdf(b"not a pdf")
