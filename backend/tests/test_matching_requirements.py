from app.matching.requirements import parse_job_requirements


def test_requirements_parser_separates_required_and_preferred_skills() -> None:
    requirements = parse_job_requirements(
        "Senior Full Stack React Developer",
        """Responsibilities
        Build reliable web applications and APIs.
        Requirements
        Must have React, TypeScript, Node.js and PostgreSQL experience.
        Nice to have
        Python, AWS and Kubernetes are a plus.
        """,
    )

    assert {"React", "TypeScript", "Node.js", "PostgreSQL"} <= requirements.required_skills
    assert {"Python", "AWS", "Kubernetes"} <= requirements.preferred_skills
    assert "delivery" in requirements.responsibility_themes
    assert requirements.confidence == "high"


def test_requirements_parser_reads_minimum_experience() -> None:
    requirements = parse_job_requirements(
        "Backend Engineer",
        """Qualifications
        At least 8 years of experience with Python and FastAPI is required.
        """,
    )

    assert requirements.minimum_years == 8
    assert {"Python", "FastAPI"} <= requirements.critical_skills
