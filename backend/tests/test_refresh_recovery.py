from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.api.routes import refresh
from app.models.common import utc_now


class FakeSession:
    def __init__(self, last_source_finish=None):
        self.last_source_finish = last_source_finish
        self.flushed = False

    async def scalar(self, _statement):
        return self.last_source_finish

    async def flush(self):
        self.flushed = True


@pytest.mark.asyncio
async def test_stale_refresh_is_failed_and_unlocked(monkeypatch) -> None:
    monkeypatch.setattr(
        refresh,
        "get_settings",
        lambda: SimpleNamespace(refresh_stale_after_seconds=900),
    )
    run = SimpleNamespace(
        id="refresh-id",
        status="running",
        stage="ingesting",
        started_at=utc_now() - timedelta(minutes=20),
        finished_at=None,
        error_summary=None,
    )
    session = FakeSession()

    expired = await refresh._expire_stale_run(session, run)

    assert expired is True
    assert run.status == "failed"
    assert run.stage == "completed"
    assert run.finished_at is not None
    assert "safely fetch again" in run.error_summary
    assert session.flushed is True


@pytest.mark.asyncio
async def test_recent_refresh_is_not_expired(monkeypatch) -> None:
    monkeypatch.setattr(
        refresh,
        "get_settings",
        lambda: SimpleNamespace(refresh_stale_after_seconds=900),
    )
    run = SimpleNamespace(
        id="refresh-id",
        status="running",
        started_at=utc_now() - timedelta(minutes=5),
    )
    session = FakeSession()

    assert await refresh._expire_stale_run(session, run) is False
    assert run.status == "running"
    assert session.flushed is False
