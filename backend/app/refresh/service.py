from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.ingestion.factory import build_source_adapter
from app.ingestion.repository import SqlAlchemyIngestionRepository
from app.ingestion.service import IngestionFailed, IngestionService
from app.ingestion.source_health import mark_source_failure
from app.matching.service import rebuild_profile_matches
from app.models.candidate_profile import CandidateProfile
from app.models.common import utc_now
from app.models.job_posting import JobPosting
from app.models.refresh_run import RefreshRun
from app.models.source_registry import SourceRegistry
from app.models.source_run import SourceRun
from app.trust.engine import TRUST_VERSION

KARACHI = ZoneInfo("Asia/Karachi")
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceRefreshResult:
    source_id: UUID
    source_name: str
    status: str
    received_count: int = 0
    new_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    deactivated_count: int = 0
    error: str | None = None


class DailyRefreshService:
    def __init__(self, refresh_run_id: UUID) -> None:
        self.refresh_run_id = refresh_run_id
        self.settings = get_settings()
        self.semaphore = asyncio.Semaphore(self.settings.refresh_source_concurrency)

    async def _ingest_source(self, source_id: UUID) -> SourceRefreshResult:
        async with self.semaphore, SessionLocal() as session:
            source = await session.get(SourceRegistry, source_id)
            if source is None:
                return SourceRefreshResult(
                    source_id,
                    "Unknown source",
                    "failed",
                    error="Missing source",
                )
            now = utc_now()
            if not source.enabled:
                return SourceRefreshResult(
                    source.id,
                    source.name,
                    "skipped",
                    error="Source disabled",
                )
            if source.circuit_open_until and source.circuit_open_until > now:
                return SourceRefreshResult(
                    source.id,
                    source.name,
                    "skipped",
                    error=f"Circuit open until {source.circuit_open_until.isoformat()}",
                )

            adapter = build_source_adapter(source, self.settings)
            logger.info(
                "refresh_source_started refresh_run_id=%s source=%s",
                self.refresh_run_id,
                source.name,
            )
            repository = SqlAlchemyIngestionRepository(
                session,
                refresh_run_id=self.refresh_run_id,
            )
            service = IngestionService(source=source, adapter=adapter, repository=repository)
            try:
                report = await asyncio.wait_for(
                    service.run(),
                    timeout=self.settings.refresh_source_timeout_seconds,
                )
                await session.commit()
                logger.info(
                    "refresh_source_succeeded refresh_run_id=%s source=%s "
                    "received=%s new=%s changed=%s",
                    self.refresh_run_id,
                    source.name,
                    report.received_count,
                    report.new_count,
                    report.changed_count,
                )
                return SourceRefreshResult(
                    source.id,
                    source.name,
                    "succeeded",
                    received_count=report.received_count,
                    new_count=report.new_count,
                    changed_count=report.changed_count,
                    unchanged_count=report.unchanged_count,
                    deactivated_count=report.deactivated_count,
                )
            except (IngestionFailed, TimeoutError) as exc:
                await session.rollback()
                error = (
                    "Source exceeded the "
                    f"{self.settings.refresh_source_timeout_seconds}-second limit"
                    if isinstance(exc, TimeoutError)
                    else str(exc)
                )
                source = await session.get(SourceRegistry, source_id)
                if source is not None:
                    mark_source_failure(
                        source,
                        error=error,
                        threshold=self.settings.source_circuit_breaker_threshold,
                        cooldown_minutes=self.settings.source_circuit_breaker_cooldown_minutes,
                    )
                    session.add(
                        SourceRun(
                            source=source,
                            refresh_run_id=self.refresh_run_id,
                            status="failed",
                            finished_at=utc_now(),
                            error_summary=error[:4000],
                        )
                    )
                    await session.commit()
                logger.warning(
                    "refresh_source_failed refresh_run_id=%s source=%s error=%s",
                    self.refresh_run_id,
                    source.name if source else source_id,
                    error,
                )
                return SourceRefreshResult(
                    source_id,
                    source.name if source else "Unknown source",
                    "failed",
                    error=error[:500],
                )
            finally:
                await adapter.close()

    async def _record_source_result(self, result: SourceRefreshResult) -> None:
        async with SessionLocal() as session:
            run = await session.get(RefreshRun, self.refresh_run_id)
            if run is None:
                return
            run.sources_completed += 1
            if result.status == "succeeded":
                run.sources_succeeded += 1
            elif result.status == "skipped":
                run.sources_skipped += 1
            else:
                run.sources_failed += 1
            run.received_count += result.received_count
            run.new_count += result.new_count
            run.changed_count += result.changed_count
            run.unchanged_count += result.unchanged_count
            run.deactivated_count += result.deactivated_count
            if result.error:
                run.failures = [
                    *run.failures,
                    {
                        "source_id": str(result.source_id),
                        "source_name": result.source_name,
                        "status": result.status,
                        "message": result.error,
                    },
                ]
            await session.commit()

    async def _finalize(self) -> None:
        async with SessionLocal() as session:
            run = await session.get(RefreshRun, self.refresh_run_id)
            if run is None:
                return
            run.stage = "classifying"
            await session.commit()

            today = datetime.now(KARACHI).date()
            base = [
                JobPosting.is_active.is_(True),
                JobPosting.is_canonical.is_(True),
                JobPosting.trust_version == TRUST_VERSION,
            ]

            async def count(*conditions: object) -> int:
                return int(
                    await session.scalar(
                        select(func.count(JobPosting.id)).where(*base, *conditions)
                    )
                    or 0
                )

            run.verified_today_count = await count(
                JobPosting.freshness_grade.in_(("A", "B")),
                JobPosting.published_local_date == today,
            )
            run.worldwide_count = await count(JobPosting.global_remote.is_(True))
            run.pakistan_eligible_count = await count(JobPosting.pakistan_eligibility == "yes")
            run.unclear_count = await count(JobPosting.pakistan_eligibility == "unknown")
            run.stage = "matching"
            await session.commit()

            profile = await session.scalar(
                select(CandidateProfile)
                .where(CandidateProfile.is_current.is_(True))
                .order_by(CandidateProfile.version.desc())
            )
            if profile is None:
                run.status = "completed_without_matching"
            else:
                result = await rebuild_profile_matches(session, profile)
                run.matches_scored = result.scored
                run.strict_matches = result.strict_visible
                run.uncertain_matches = result.uncertain_visible
                run.excluded_matches = result.excluded
                run.status = "completed_with_errors" if run.failures else "completed"
            run.stage = "completed"
            run.finished_at = utc_now()
            await session.commit()
            logger.info(
                "refresh_completed refresh_run_id=%s status=%s scored=%s failures=%s",
                self.refresh_run_id,
                run.status,
                run.matches_scored,
                len(run.failures),
            )

    async def run(self) -> None:
        try:
            async with SessionLocal() as session:
                run = await session.get(RefreshRun, self.refresh_run_id)
                if run is None:
                    return
                source_ids = list(
                    await session.scalars(
                        select(SourceRegistry.id)
                        .where(SourceRegistry.enabled.is_(True))
                        .order_by(SourceRegistry.name)
                    )
                )
                run.status = "running"
                run.stage = "ingesting"
                run.sources_total = len(source_ids)
                await session.commit()
                logger.info(
                    "refresh_started refresh_run_id=%s sources_total=%s",
                    self.refresh_run_id,
                    len(source_ids),
                )

            tasks = [
                asyncio.create_task(self._ingest_source(source_id)) for source_id in source_ids
            ]
            for task in asyncio.as_completed(tasks):
                await self._record_source_result(await task)
            await self._finalize()
        except Exception as exc:
            async with SessionLocal() as session:
                run = await session.get(RefreshRun, self.refresh_run_id)
                if run is not None:
                    run.status = "failed"
                    run.stage = "completed"
                    run.finished_at = utc_now()
                    run.error_summary = str(exc)[:1000]
                    await session.commit()
            logger.exception("refresh_failed refresh_run_id=%s", self.refresh_run_id)
