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
    assert result.score == 98
    assert result.score_label == "Strong match"
    assert result.components == {
        "required_core_skills": 35,
        "role_title": 20,
        "seniority_leadership": 15,
        "architecture_cloud_domain": 15,
        "work_arrangement": 8,
        "freshness": 5,
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
    assert result.score == 94
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
    assert "Node.js" in facts.skills["backend"]
    assert "ai_llm" in facts.role_families
    assert not hasattr(facts, "email")


def test_resume_parser_rejects_non_pdf_content() -> None:
    with pytest.raises(ValueError, match="valid PDF"):
        parse_resume_pdf(b"not a pdf")
