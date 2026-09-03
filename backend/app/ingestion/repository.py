from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.contracts import IngestionReport, NormalizedJob
from app.ingestion.source_health import mark_source_success
from app.models.common import utc_now
from app.models.job_posting import JobPosting
from app.models.job_snapshot import JobSnapshot
from app.models.source_registry import SourceRegistry
from app.models.source_run import SourceRun
from app.trust.engine import (
    TRUST_VERSION,
    TrustClassification,
    classify_job,
    description_similarity,
)


class SqlAlchemyIngestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start_run(self, source: SourceRegistry) -> SourceRun:
        run = SourceRun(source=source, status="running")
        self.session.add(run)
        await self.session.flush()
        return run

    async def find_posting(self, source_id: UUID, source_job_id: str) -> JobPosting | None:
        statement = select(JobPosting).where(
            JobPosting.source_registry_id == source_id,
            JobPosting.source_job_id == source_job_id,
        )
        return await self.session.scalar(statement)

    async def _find_duplicate(
        self,
        trust: TrustClassification,
        description_text: str,
        *,
        exclude_id: UUID | None = None,
    ) -> JobPosting | None:
        statement = select(JobPosting).where(
            JobPosting.dedupe_key == trust.dedupe_key,
            JobPosting.is_active.is_(True),
            JobPosting.trust_version == TRUST_VERSION,
        )
        if exclude_id:
            statement = statement.where(JobPosting.id != exclude_id)
        candidates = list((await self.session.scalars(statement.limit(20))).all())
        for candidate in candidates:
            if candidate.description_fingerprint == trust.description_fingerprint:
                return candidate
            if description_similarity(candidate.description_text, description_text) >= 0.82:
                return candidate
        return None

    @staticmethod
    def _apply_trust(posting: JobPosting, trust: TrustClassification) -> None:
        posting.normalized_title = trust.normalized_title
        posting.normalized_employment_type = trust.normalized_employment_type
        posting.normalized_compensation = trust.normalized_compensation
        posting.structured_locations = trust.structured_locations
        posting.sanitized_description_html = trust.sanitized_description_html
        posting.freshness_grade = trust.freshness_grade
        posting.freshness_label = trust.freshness_label
        posting.published_local_date = trust.published_local_date
        posting.is_reposted = trust.is_reposted
        posting.reposted_at = trust.reposted_at
        posting.remote_mode = trust.remote_mode
        posting.pakistan_eligibility = trust.pakistan_eligibility
        posting.eligibility_positive_evidence = trust.positive_evidence
        posting.eligibility_negative_evidence = trust.negative_evidence
        posting.employer_headquarters_gcc = trust.employer_headquarters_gcc
        posting.job_location_gcc = trust.job_location_gcc
        posting.description_fingerprint = trust.description_fingerprint
        posting.dedupe_key = trust.dedupe_key
        posting.trust_version = TRUST_VERSION

    async def _promote_family(self, canonical_id: UUID, *, exclude_id: UUID) -> None:
        members = list(
            (
                await self.session.scalars(
                    select(JobPosting)
                    .where(
                        JobPosting.canonical_job_id == canonical_id,
                        JobPosting.id != exclude_id,
                        JobPosting.is_active.is_(True),
                    )
                    .order_by(JobPosting.first_seen_at)
                )
            ).all()
        )
        if not members:
            return
        promoted = members[0]
        await self.session.execute(
            update(JobPosting)
            .where(JobPosting.canonical_job_id == canonical_id)
            .values(canonical_job_id=promoted.id, is_canonical=False)
        )
        promoted.canonical_job_id = promoted.id
        promoted.is_canonical = True

    async def save_new_posting(self, source: SourceRegistry, job: NormalizedJob) -> JobPosting:
        trust = classify_job(
            job,
            source_type=source.source_type,
            employer_headquarters_gcc=source.is_gcc,
        )
        duplicate = await self._find_duplicate(trust, job.description_text)
        now = utc_now()
        posting = JobPosting(
            source_registry_id=source.id,
            source_job_id=job.source_job_id,
            employer_name=job.employer_name,
            title=job.title,
            normalized_title=trust.normalized_title,
            location_text=job.location_text,
            structured_locations=trust.structured_locations,
            description_html=job.description_html,
            sanitized_description_html=trust.sanitized_description_html,
            description_text=job.description_text,
            source_url=job.source_url or job.application_url,
            application_url=job.application_url,
            workplace_type=job.workplace_type,
            employment_type=job.employment_type,
            normalized_employment_type=trust.normalized_employment_type,
            compensation=job.compensation,
            normalized_compensation=trust.normalized_compensation,
            attribution_name=job.attribution_name,
            attribution_url=job.attribution_url,
            first_published_at=job.first_published_at,
            source_updated_at=job.source_updated_at,
            last_verified_at=now,
            freshness_grade=trust.freshness_grade,
            freshness_label=trust.freshness_label,
            published_local_date=trust.published_local_date,
            is_reposted=trust.is_reposted,
            reposted_at=trust.reposted_at,
            remote_mode=trust.remote_mode,
            pakistan_eligibility=trust.pakistan_eligibility,
            eligibility_positive_evidence=trust.positive_evidence,
            eligibility_negative_evidence=trust.negative_evidence,
            employer_headquarters_gcc=trust.employer_headquarters_gcc,
            job_location_gcc=trust.job_location_gcc,
            description_fingerprint=trust.description_fingerprint,
            dedupe_key=trust.dedupe_key,
            trust_version=TRUST_VERSION,
            current_content_hash=job.content_hash,
            is_active=True,
        )
        self.session.add(posting)
        await self.session.flush()
        if duplicate:
            posting.canonical_job_id = duplicate.canonical_job_id or duplicate.id
            posting.is_canonical = False
        else:
            posting.canonical_job_id = posting.id
            posting.is_canonical = True
        await self.session.flush()
        return posting

    async def update_posting(
        self,
        source: SourceRegistry,
        posting: JobPosting,
        job: NormalizedJob,
    ) -> None:
        previous_published_at = posting.first_published_at
        previous_canonical_id = posting.canonical_job_id or posting.id
        previous_dedupe_key = posting.dedupe_key
        trust = classify_job(
            job,
            source_type=source.source_type,
            employer_headquarters_gcc=source.is_gcc,
            prior_published_at=previous_published_at,
        )
        duplicate = await self._find_duplicate(
            trust,
            job.description_text,
            exclude_id=posting.id,
        )
        posting.employer_name = job.employer_name
        posting.title = job.title
        posting.location_text = job.location_text
        posting.description_html = job.description_html
        posting.description_text = job.description_text
        posting.source_url = job.source_url or job.application_url
        posting.application_url = job.application_url
        posting.workplace_type = job.workplace_type
        posting.employment_type = job.employment_type
        posting.compensation = job.compensation
        posting.attribution_name = job.attribution_name
        posting.attribution_url = job.attribution_url
        posting.first_published_at = job.first_published_at
        posting.source_updated_at = job.source_updated_at
        posting.last_verified_at = utc_now()
        posting.closed_at = None
        posting.current_content_hash = job.content_hash
        posting.last_seen_active_at = utc_now()
        posting.is_active = True
        self._apply_trust(posting, trust)
        if duplicate:
            posting.canonical_job_id = duplicate.canonical_job_id or duplicate.id
            posting.is_canonical = False
        elif previous_dedupe_key != trust.dedupe_key or not posting.canonical_job_id:
            posting.canonical_job_id = posting.id
            posting.is_canonical = True
        if posting.is_canonical is False and previous_canonical_id == posting.id:
            await self._promote_family(previous_canonical_id, exclude_id=posting.id)
        await self.session.flush()

    async def touch_posting(self, posting: JobPosting) -> None:
        posting.last_seen_active_at = utc_now()
        posting.last_verified_at = utc_now()
        posting.closed_at = None
        posting.is_active = True
        await self.session.flush()

    async def add_snapshot(self, posting: JobPosting, job: NormalizedJob) -> bool:
        exists = await self.session.scalar(
            select(JobSnapshot.id).where(
                JobSnapshot.job_posting_id == posting.id,
                JobSnapshot.content_hash == job.content_hash,
            )
        )
        if exists:
            return False
        self.session.add(
            JobSnapshot(
                job_posting_id=posting.id,
                content_hash=job.content_hash,
                payload=job.raw_payload,
            )
        )
        await self.session.flush()
        return True

    async def deactivate_missing(self, source_id: UUID, seen_source_job_ids: set[str]) -> int:
        missing_statement = select(JobPosting).where(
            JobPosting.source_registry_id == source_id,
            JobPosting.is_active.is_(True),
        )
        if seen_source_job_ids:
            missing_statement = missing_statement.where(
                JobPosting.source_job_id.not_in(seen_source_job_ids)
            )
        missing = list((await self.session.scalars(missing_statement)).all())
        now = utc_now()
        statement = (
            update(JobPosting)
            .where(
                JobPosting.source_registry_id == source_id,
                JobPosting.is_active.is_(True),
            )
            .values(is_active=False, closed_at=now, last_verified_at=now)
        )
        if seen_source_job_ids:
            statement = statement.where(JobPosting.source_job_id.not_in(seen_source_job_ids))
        result = await self.session.execute(statement)
        for posting in missing:
            if posting.is_canonical:
                await self._promote_family(posting.id, exclude_id=posting.id)
        return int(result.rowcount or 0)

    async def finish_run(self, run: SourceRun, report: IngestionReport) -> None:
        run.status = "succeeded"
        run.finished_at = utc_now()
        run.received_count = report.received_count
        run.new_count = report.new_count
        run.changed_count = report.changed_count
        run.unchanged_count = report.unchanged_count
        run.deactivated_count = report.deactivated_count
        mark_source_success(
            run.source,
            job_count=report.received_count,
            sample_url=report.sample_url,
        )
        await self.session.flush()

    async def fail_run(self, run: SourceRun, error: str) -> None:
        run.status = "failed"
        run.finished_at = utc_now()
        run.error_summary = error[:4000]
        await self.session.flush()
