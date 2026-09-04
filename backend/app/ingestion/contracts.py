from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.models.job_posting import JobPosting
from app.models.source_registry import SourceRegistry
from app.models.source_run import SourceRun


@dataclass(frozen=True, slots=True)
class SourceJobSummary:
    source_job_id: str
    title: str
    location_text: str | None
    application_url: str
    source_updated_at: datetime | None
    raw_payload: dict[str, Any]
    force_normalize: bool = False


@dataclass(frozen=True, slots=True)
class NormalizedJob:
    source_job_id: str
    employer_name: str
    title: str
    location_text: str | None
    description_html: str
    description_text: str
    application_url: str
    first_published_at: datetime | None
    source_updated_at: datetime | None
    content_hash: str
    raw_payload: dict[str, Any]
    source_url: str | None = None
    workplace_type: str | None = None
    employment_type: str | None = None
    compensation: dict[str, Any] | None = None
    attribution_name: str | None = None
    attribution_url: str | None = None
    source_country_codes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IngestionReport:
    source_id: UUID
    run_id: UUID
    received_count: int = 0
    new_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    deactivated_count: int = 0
    sample_url: str | None = None


class SourceAdapter(Protocol):
    async def list_jobs(self) -> list[SourceJobSummary]: ...

    async def fetch_and_normalize(self, summary: SourceJobSummary) -> NormalizedJob: ...

    async def close(self) -> None: ...


class IngestionRepository(Protocol):
    async def start_run(self, source: SourceRegistry) -> SourceRun: ...

    async def find_posting(self, source_id: UUID, source_job_id: str) -> JobPosting | None: ...

    async def save_new_posting(self, source: SourceRegistry, job: NormalizedJob) -> JobPosting: ...

    async def update_posting(
        self,
        source: SourceRegistry,
        posting: JobPosting,
        job: NormalizedJob,
    ) -> None: ...

    async def touch_posting(self, posting: JobPosting) -> None: ...

    async def add_snapshot(self, posting: JobPosting, job: NormalizedJob) -> bool: ...

    async def deactivate_missing(self, source_id: UUID, seen_source_job_ids: set[str]) -> int: ...

    async def finish_run(self, run: SourceRun, report: IngestionReport) -> None: ...

    async def fail_run(self, run: SourceRun, error: str) -> None: ...
