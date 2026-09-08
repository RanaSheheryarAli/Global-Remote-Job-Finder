from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting
from app.models.job_rejection import JobRejection


@dataclass(frozen=True, slots=True)
class CleanupResult:
    cutoff: datetime
    deleted_jobs: int
    deleted_rejections: int


def retention_cutoff(*, hours: int, now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)) - timedelta(hours=hours)


async def delete_expired_jobs(session: AsyncSession, *, hours: int = 24) -> CleanupResult:
    cutoff = retention_cutoff(hours=hours)
    job_age = func.coalesce(JobPosting.first_published_at, JobPosting.first_seen_at)
    expired = job_age < cutoff

    expired_canonical_ids = list(
        await session.scalars(
            select(JobPosting.id).where(expired, JobPosting.is_canonical.is_(True))
        )
    )
    for canonical_id in expired_canonical_ids:
        survivor = await session.scalar(
            select(JobPosting)
            .where(
                JobPosting.canonical_job_id == canonical_id,
                JobPosting.id != canonical_id,
                job_age >= cutoff,
            )
            .order_by(JobPosting.first_seen_at)
            .limit(1)
        )
        if survivor is None:
            continue
        await session.execute(
            update(JobPosting)
            .where(
                JobPosting.canonical_job_id == canonical_id,
                JobPosting.id != canonical_id,
                job_age >= cutoff,
            )
            .values(canonical_job_id=survivor.id, is_canonical=False)
        )
        survivor.canonical_job_id = survivor.id
        survivor.is_canonical = True

    deleted_jobs = await session.execute(
        delete(JobPosting).where(expired).execution_options(synchronize_session=False)
    )
    deleted_rejections = await session.execute(
        delete(JobRejection)
        .where(JobRejection.last_rejected_at < cutoff)
        .execution_options(synchronize_session=False)
    )
    await session.flush()
    return CleanupResult(
        cutoff=cutoff,
        deleted_jobs=int(deleted_jobs.rowcount or 0),
        deleted_rejections=int(deleted_rejections.rowcount or 0),
    )
