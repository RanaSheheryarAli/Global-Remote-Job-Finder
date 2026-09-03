from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ingestion.contracts import NormalizedJob, SourceJobSummary
from app.ingestion.service import IngestionFailed, IngestionService


class FakeAdapter:
    def __init__(self, summaries, details):
        self.summaries = summaries
        self.details = details
        self.detail_calls = 0

    async def list_jobs(self):
        return self.summaries

    async def fetch_and_normalize(self, summary):
        self.detail_calls += 1
        return self.details[summary.source_job_id]


class FailingAdapter:
    async def list_jobs(self):
        raise RuntimeError("source unavailable")

    async def fetch_and_normalize(self, summary):
        raise AssertionError("detail fetch should not run")


class FakeRepository:
    def __init__(self, existing=None, deactivated=0):
        self.existing = existing or {}
        self.deactivated = deactivated
        self.snapshots = []
        self.updates = 0
        self.run = SimpleNamespace(id=uuid4(), source=None, status="running")

    async def start_run(self, source):
        self.run.source = source
        return self.run

    async def find_posting(self, source_id, source_job_id):
        return self.existing.get(source_job_id)

    async def save_new_posting(self, source, job):
        posting = SimpleNamespace(
            id=uuid4(),
            source_job_id=job.source_job_id,
            source_updated_at=job.source_updated_at,
            current_content_hash=job.content_hash,
            is_active=True,
        )
        self.existing[job.source_job_id] = posting
        return posting

    async def update_posting(self, source, posting, job):
        self.updates += 1
        posting.current_content_hash = job.content_hash
        posting.source_updated_at = job.source_updated_at
        posting.is_active = True
        posting.trust_version = 1

    async def touch_posting(self, posting):
        posting.is_active = True

    async def add_snapshot(self, posting, job):
        self.snapshots.append((posting.id, job.content_hash))
        return True

    async def deactivate_missing(self, source_id, seen_source_job_ids):
        return self.deactivated

    async def finish_run(self, run, report):
        run.status = "succeeded"

    async def fail_run(self, run, error):
        run.status = "failed"


def make_summary(job_id="101"):
    updated = datetime(2026, 9, 3, 9, 30, tzinfo=UTC)
    return SourceJobSummary(job_id, "Engineer", "Remote", "https://example/jobs/101", updated, {})


def make_job(job_id="101", content_hash="a" * 64):
    updated = datetime(2026, 9, 3, 9, 30, tzinfo=UTC)
    return NormalizedJob(
        source_job_id=job_id,
        employer_name="Example Company",
        title="Engineer",
        location_text="Remote",
        description_html="<p>Role</p>",
        description_text="Role",
        application_url="https://example/jobs/101",
        first_published_at=updated,
        source_updated_at=updated,
        content_hash=content_hash,
        raw_payload={},
    )


@pytest.mark.asyncio
async def test_new_job_is_persisted_with_snapshot() -> None:
    source = SimpleNamespace(id=uuid4())
    adapter = FakeAdapter([make_summary()], {"101": make_job()})
    repository = FakeRepository()
    report = await IngestionService(source=source, adapter=adapter, repository=repository).run()

    assert report.new_count == 1
    assert report.changed_count == 0
    assert adapter.detail_calls == 1
    assert len(repository.snapshots) == 1
    assert repository.run.status == "succeeded"


@pytest.mark.asyncio
async def test_unchanged_job_skips_detail_fetch() -> None:
    source = SimpleNamespace(id=uuid4())
    summary = make_summary()
    existing = SimpleNamespace(
        id=uuid4(),
        source_updated_at=summary.source_updated_at,
        current_content_hash="a" * 64,
        is_active=True,
        trust_version=1,
    )
    adapter = FakeAdapter([summary], {"101": make_job()})
    repository = FakeRepository(existing={"101": existing})
    report = await IngestionService(source=source, adapter=adapter, repository=repository).run()

    assert report.unchanged_count == 1
    assert adapter.detail_calls == 0
    assert repository.snapshots == []


@pytest.mark.asyncio
async def test_missing_update_timestamp_forces_detail_check() -> None:
    source = SimpleNamespace(id=uuid4())
    summary = SourceJobSummary(
        "101",
        "Engineer",
        "Remote",
        "https://example/jobs/101",
        None,
        {},
    )
    existing = SimpleNamespace(
        id=uuid4(),
        source_updated_at=None,
        current_content_hash="a" * 64,
        is_active=True,
        trust_version=1,
    )
    adapter = FakeAdapter([summary], {"101": make_job()})
    repository = FakeRepository(existing={"101": existing})
    report = await IngestionService(source=source, adapter=adapter, repository=repository).run()

    assert report.unchanged_count == 1
    assert adapter.detail_calls == 1


@pytest.mark.asyncio
async def test_unchanged_job_is_enriched_when_trust_version_is_old() -> None:
    source = SimpleNamespace(id=uuid4())
    summary = make_summary()
    existing = SimpleNamespace(
        id=uuid4(),
        source_updated_at=summary.source_updated_at,
        current_content_hash="a" * 64,
        is_active=True,
        trust_version=0,
    )
    adapter = FakeAdapter([summary], {"101": make_job()})
    repository = FakeRepository(existing={"101": existing})

    report = await IngestionService(
        source=source,
        adapter=adapter,
        repository=repository,
    ).run()

    assert report.unchanged_count == 1
    assert adapter.detail_calls == 1
    assert repository.updates == 1
    assert existing.trust_version == 1
    assert repository.snapshots == []


@pytest.mark.asyncio
async def test_changed_job_gets_new_snapshot() -> None:
    source = SimpleNamespace(id=uuid4())
    summary = make_summary()
    existing = SimpleNamespace(
        id=uuid4(),
        source_updated_at=datetime(2026, 9, 3, 8, 30, tzinfo=UTC),
        current_content_hash="a" * 64,
        is_active=True,
        trust_version=1,
    )
    adapter = FakeAdapter([summary], {"101": make_job(content_hash="b" * 64)})
    repository = FakeRepository(existing={"101": existing})
    report = await IngestionService(source=source, adapter=adapter, repository=repository).run()

    assert report.changed_count == 1
    assert existing.current_content_hash == "b" * 64
    assert len(repository.snapshots) == 1


@pytest.mark.asyncio
async def test_failed_source_marks_run_failed() -> None:
    source = SimpleNamespace(id=uuid4())
    repository = FakeRepository()

    with pytest.raises(IngestionFailed, match="source unavailable"):
        await IngestionService(
            source=source,
            adapter=FailingAdapter(),
            repository=repository,
        ).run()

    assert repository.run.status == "failed"
