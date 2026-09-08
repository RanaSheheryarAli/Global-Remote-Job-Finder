import pytest

from app.relevance.engine import classify_job_relevance


@pytest.mark.parametrize(
    "title",
    [
        "Senior Software Engineer",
        "Full Stack React Developer",
        "Backend Python Engineer",
        "iOS Developer",
        "DevOps Engineer",
        "QA Automation Engineer",
    ],
)
def test_supported_engineering_titles_are_accepted(title: str) -> None:
    decision = classify_job_relevance(title)

    assert decision.accepted is True
    assert decision.confidence == "high"


@pytest.mark.parametrize(
    "title",
    [
        "Office Operations Associate",
        "Territory Account Executive, Indonesia",
        "Senior Territory Account Executive - Beijing",
        "Talent Acquisition Partner",
        "Product Marketing Manager",
    ],
)
def test_non_engineering_titles_are_rejected(title: str) -> None:
    decision = classify_job_relevance(title)

    assert decision.accepted is False
    assert decision.confidence == "high"


def test_ambiguous_title_can_be_confirmed_by_description() -> None:
    decision = classify_job_relevance(
        "Technical Specialist",
        "Build and maintain React and TypeScript applications. Implement REST API features.",
    )

    assert decision.accepted is True
    assert decision.confidence == "medium"


def test_ambiguous_title_without_engineering_evidence_is_rejected() -> None:
    decision = classify_job_relevance(
        "Associate",
        "Coordinate office schedules, vendors, and administrative requests.",
    )

    assert decision.accepted is False
