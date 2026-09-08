from datetime import timedelta
from types import SimpleNamespace

from app.ingestion import rate_limits


def test_remotive_refresh_is_rate_limited_for_six_hours(monkeypatch) -> None:
    now = rate_limits.utc_now()
    source = SimpleNamespace(source_type="remotive", last_success_at=now - timedelta(hours=2))
    monkeypatch.setattr(rate_limits, "utc_now", lambda: now)

    retry_after = rate_limits.retry_after_seconds(source)

    assert retry_after == 4 * 60 * 60


def test_direct_ats_source_has_no_feed_cooldown() -> None:
    source = SimpleNamespace(source_type="greenhouse", last_success_at=rate_limits.utc_now())

    assert rate_limits.retry_after_seconds(source) is None


def test_expired_public_feed_cooldown_allows_refresh(monkeypatch) -> None:
    now = rate_limits.utc_now()
    source = SimpleNamespace(source_type="jobicy", last_success_at=now - timedelta(hours=2))
    monkeypatch.setattr(rate_limits, "utc_now", lambda: now)

    assert rate_limits.retry_after_seconds(source) is None
