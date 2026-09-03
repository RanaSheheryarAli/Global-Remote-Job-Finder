from datetime import timedelta

from app.models.common import utc_now
from app.models.source_registry import SourceRegistry


def mark_source_success(
    source: SourceRegistry,
    *,
    job_count: int,
    sample_url: str | None = None,
) -> None:
    now = utc_now()
    source.health_status = "healthy"
    source.last_checked_at = now
    source.last_success_at = now
    source.consecutive_failures = 0
    source.circuit_open_until = None
    source.last_job_count = job_count
    source.last_error_summary = None
    if sample_url:
        source.validated_at = now
        source.validation_sample_url = sample_url


def mark_source_failure(
    source: SourceRegistry,
    *,
    error: str,
    threshold: int,
    cooldown_minutes: int,
) -> None:
    now = utc_now()
    source.last_checked_at = now
    source.last_failure_at = now
    source.consecutive_failures += 1
    source.last_error_summary = error[:4000]
    if source.consecutive_failures >= threshold:
        source.health_status = "failing"
        source.circuit_open_until = now + timedelta(minutes=cooldown_minutes)
    else:
        source.health_status = "degraded"
