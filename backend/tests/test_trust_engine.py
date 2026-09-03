from datetime import UTC, datetime

from app.ingestion.contracts import NormalizedJob
from app.trust.engine import (
    classify_job,
    description_similarity,
    is_strict_today,
    sanitize_html,
)


def make_job(**overrides) -> NormalizedJob:
    values = {
        "source_job_id": "job-1",
        "employer_name": "Example",
        "title": "Senior Backend Engineer",
        "location_text": "Remote - Worldwide",
        "description_html": "<p>Work from anywhere.</p>",
        "description_text": "This is a fully remote role. Work from anywhere.",
        "application_url": "https://example.com/apply",
        "first_published_at": datetime(2026, 9, 2, 20, 30, tzinfo=UTC),
        "source_updated_at": None,
        "content_hash": "a" * 64,
        "raw_payload": {},
        "workplace_type": "remote",
        "employment_type": "Full Time",
        "compensation": {"compensationTierSummary": "$120K - $150K"},
    }
    values.update(overrides)
    return NormalizedJob(**values)


def test_verified_timestamp_uses_karachi_calendar_date() -> None:
    result = classify_job(make_job(), source_type="ashby", employer_headquarters_gcc=False)
    assert result.freshness_grade == "A"
    assert result.published_local_date.isoformat() == "2026-09-03"
    assert is_strict_today(result, now=datetime(2026, 9, 3, 8, tzinfo=UTC))


def test_first_seen_only_never_becomes_strict_today() -> None:
    result = classify_job(
        make_job(first_published_at=None),
        source_type="lever",
        employer_headquarters_gcc=False,
    )
    assert result.freshness_grade == "C"
    assert result.published_local_date is None
    assert not is_strict_today(result, now=datetime(2026, 9, 3, tzinfo=UTC))


def test_restricted_remote_role_is_not_pakistan_eligible() -> None:
    result = classify_job(
        make_job(
            location_text="Remote - United States only",
            description_text="This is a fully remote role within the United States.",
        ),
        source_type="greenhouse",
        employer_headquarters_gcc=False,
    )
    assert result.remote_mode == "remote"
    assert result.pakistan_eligibility == "no"
    assert result.negative_evidence


def test_conflicting_location_evidence_stays_unknown() -> None:
    result = classify_job(
        make_job(
            description_text=("Work from anywhere. Candidates must be based in the United States.")
        ),
        source_type="greenhouse",
        employer_headquarters_gcc=False,
    )
    assert result.pakistan_eligibility == "unknown"
    assert result.positive_evidence and result.negative_evidence


def test_gulf_facts_remain_separate() -> None:
    result = classify_job(
        make_job(location_text="Dubai, United Arab Emirates", description_text="Remote role."),
        source_type="ashby",
        employer_headquarters_gcc=False,
    )
    assert result.employer_headquarters_gcc is False
    assert result.job_location_gcc is True
    assert result.pakistan_eligibility == "unknown"


def test_republication_is_explicit() -> None:
    prior = datetime(2026, 9, 1, tzinfo=UTC)
    result = classify_job(
        make_job(first_published_at=datetime(2026, 9, 3, tzinfo=UTC)),
        source_type="ashby",
        employer_headquarters_gcc=False,
        prior_published_at=prior,
    )
    assert result.is_reposted is True
    assert result.reposted_at is not None
    assert result.freshness_label.startswith("Republished")


def test_html_sanitizer_removes_executable_content() -> None:
    value = '<p>Hello<script>alert(1)</script><a href="javascript:x">bad</a></p>'
    assert sanitize_html(value) == "<p>Hello<a>bad</a></p>"


def test_description_similarity_supports_cross_source_deduplication() -> None:
    left = "Build reliable distributed APIs using Python FastAPI and PostgreSQL."
    right = "Build reliable distributed APIs using Python, FastAPI, and PostgreSQL."
    assert description_similarity(left, right) > 0.8


def test_cross_source_duplicate_uses_same_stable_key() -> None:
    greenhouse = classify_job(
        make_job(source_job_id="greenhouse-1"),
        source_type="greenhouse",
        employer_headquarters_gcc=False,
    )
    ashby = classify_job(
        make_job(source_job_id="ashby-99", title="Senior Backend Engineer!"),
        source_type="ashby",
        employer_headquarters_gcc=False,
    )
    assert greenhouse.dedupe_key == ashby.dedupe_key
    assert greenhouse.description_fingerprint == ashby.description_fingerprint


def test_normalization_preserves_original_but_creates_comparable_fields() -> None:
    result = classify_job(make_job(), source_type="greenhouse", employer_headquarters_gcc=False)
    assert result.normalized_title == "senior backend engineer"
    assert result.normalized_employment_type == "full-time"
    assert result.normalized_compensation == {
        "min": 120000.0,
        "max": 150000.0,
        "currency": "USD",
        "interval": None,
        "summary": "$120K - $150K",
    }
