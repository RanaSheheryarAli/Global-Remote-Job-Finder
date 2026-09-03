from __future__ import annotations

from app.ingestion.contracts import (
    IngestionReport,
    IngestionRepository,
    SourceAdapter,
)
from app.models.source_registry import SourceRegistry
from app.trust.engine import TRUST_VERSION


class IngestionFailed(RuntimeError):
    pass


class IngestionService:
    def __init__(
        self,
        *,
        source: SourceRegistry,
        adapter: SourceAdapter,
        repository: IngestionRepository,
    ) -> None:
        self.source = source
        self.adapter = adapter
        self.repository = repository

    async def run(self) -> IngestionReport:
        run = await self.repository.start_run(self.source)
        report = IngestionReport(source_id=self.source.id, run_id=run.id)
        try:
            summaries = await self.adapter.list_jobs()
            report.received_count = len(summaries)
            seen: set[str] = set()

            for summary in summaries:
                seen.add(summary.source_job_id)
                existing = await self.repository.find_posting(self.source.id, summary.source_job_id)
                trust_upgrade_required = bool(
                    existing and getattr(existing, "trust_version", 0) != TRUST_VERSION
                )
                detail_required = (
                    existing is None
                    or summary.force_normalize
                    or summary.source_updated_at is None
                    or existing.source_updated_at != summary.source_updated_at
                    or not existing.is_active
                    or trust_upgrade_required
                )
                if not detail_required:
                    await self.repository.touch_posting(existing)
                    report.unchanged_count += 1
                    continue

                job = await self.adapter.fetch_and_normalize(summary)
                if report.sample_url is None:
                    report.sample_url = job.source_url or job.application_url
                if existing is None:
                    posting = await self.repository.save_new_posting(self.source, job)
                    await self.repository.add_snapshot(posting, job)
                    report.new_count += 1
                elif existing.current_content_hash != job.content_hash:
                    await self.repository.update_posting(self.source, existing, job)
                    await self.repository.add_snapshot(existing, job)
                    report.changed_count += 1
                elif trust_upgrade_required:
                    await self.repository.update_posting(self.source, existing, job)
                    report.unchanged_count += 1
                else:
                    await self.repository.touch_posting(existing)
                    report.unchanged_count += 1

            report.deactivated_count = await self.repository.deactivate_missing(
                self.source.id, seen
            )
            await self.repository.finish_run(run, report)
            return report
        except Exception as exc:
            await self.repository.fail_run(run, str(exc))
            raise IngestionFailed(f"Source ingestion failed: {exc}") from exc
