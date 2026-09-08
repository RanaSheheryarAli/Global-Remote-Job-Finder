from datetime import UTC, datetime, timedelta

from app.jobs.cleanup import retention_cutoff


def test_retention_cutoff_keeps_the_latest_24_hours() -> None:
    now = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)

    assert retention_cutoff(hours=24, now=now) == now - timedelta(days=1)


def test_retention_cutoff_supports_longer_admin_retention() -> None:
    now = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)

    assert retention_cutoff(hours=72, now=now) == now - timedelta(days=3)
