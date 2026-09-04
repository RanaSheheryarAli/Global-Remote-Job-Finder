from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.job_posting import JobPosting
from app.models.source_registry import SourceRegistry
from app.schemas.job import (
    FreshnessGrade,
    JobDetailRead,
    JobListRead,
    JobRead,
    JobTrustSummary,
    PakistanEligibility,
    RemoteMode,
)
from app.trust.engine import TRUST_VERSION

router = APIRouter(prefix="/jobs", tags=["jobs"])
KARACHI = ZoneInfo("Asia/Karachi")


def _job_read(posting: JobPosting, source: SourceRegistry) -> JobRead:
    excerpt = " ".join(posting.description_text.split())[:360]
    return JobRead(
        id=posting.id,
        canonical_job_id=posting.canonical_job_id,
        source_name=source.name,
        source_type=source.source_type,
        source_job_id=posting.source_job_id,
        employer_name=posting.employer_name,
        title=posting.title,
        normalized_title=posting.normalized_title,
        location_text=posting.location_text,
        structured_locations=posting.structured_locations,
        description_excerpt=excerpt,
        source_url=posting.source_url,
        application_url=posting.application_url,
        normalized_employment_type=posting.normalized_employment_type,
        normalized_compensation=posting.normalized_compensation,
        attribution_name=posting.attribution_name,
        attribution_url=posting.attribution_url,
        first_published_at=posting.first_published_at,
        source_updated_at=posting.source_updated_at,
        first_seen_at=posting.first_seen_at,
        last_verified_at=posting.last_verified_at,
        freshness_grade=posting.freshness_grade,
        freshness_label=posting.freshness_label,
        published_local_date=posting.published_local_date,
        is_reposted=posting.is_reposted,
        remote_mode=posting.remote_mode,
        pakistan_eligibility=posting.pakistan_eligibility,
        eligibility_positive_evidence=posting.eligibility_positive_evidence,
        eligibility_negative_evidence=posting.eligibility_negative_evidence,
        geographic_scope=posting.geographic_scope,
        allowed_country_codes=posting.allowed_country_codes,
        excluded_country_codes=posting.excluded_country_codes,
        allowed_regions=posting.allowed_regions,
        residency_required=posting.residency_required,
        work_authorization_required=posting.work_authorization_required,
        timezone_constraints=posting.timezone_constraints,
        global_remote=posting.global_remote,
        eligibility_confidence=posting.eligibility_confidence,
        geographic_positive_evidence=posting.geographic_positive_evidence,
        geographic_restrictive_evidence=posting.geographic_restrictive_evidence,
        geographic_conflicting_evidence=posting.geographic_conflicting_evidence,
        discovered_refresh_run_id=posting.discovered_refresh_run_id,
        updated_refresh_run_id=posting.updated_refresh_run_id,
        employer_headquarters_gcc=posting.employer_headquarters_gcc,
        job_location_gcc=posting.job_location_gcc,
        is_active=posting.is_active,
    )


@router.get("/trust/summary", response_model=JobTrustSummary)
async def trust_summary(session: AsyncSession = Depends(get_session)) -> JobTrustSummary:
    today = datetime.now(KARACHI).date()
    base = [JobPosting.trust_version == TRUST_VERSION, JobPosting.is_active.is_(True)]

    async def count(*extra: object) -> int:
        statement = select(func.count(JobPosting.id)).where(*base, *extra)
        return int(await session.scalar(statement) or 0)

    freshness = {
        grade: await count(JobPosting.freshness_grade == grade) for grade in ("A", "B", "C", "D")
    }
    strict_conditions = (
        JobPosting.is_canonical.is_(True),
        JobPosting.freshness_grade.in_(("A", "B")),
        JobPosting.published_local_date == today,
        JobPosting.remote_mode == "remote",
        JobPosting.pakistan_eligibility == "yes",
    )
    return JobTrustSummary(
        local_date=today,
        trusted_active=await count(),
        canonical_active=await count(JobPosting.is_canonical.is_(True)),
        strict_today=await count(*strict_conditions),
        pakistan_yes=await count(JobPosting.pakistan_eligibility == "yes"),
        pakistan_unknown=await count(JobPosting.pakistan_eligibility == "unknown"),
        worldwide=await count(JobPosting.global_remote.is_(True)),
        freshness=freshness,
    )


@router.get("", response_model=JobListRead)
async def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    strict_today: bool = False,
    eligibility: PakistanEligibility | None = None,
    remote_mode: RemoteMode | None = None,
    freshness_grade: FreshnessGrade | None = None,
    gulf_employer: bool | None = None,
    gulf_location: bool | None = None,
    q: str | None = Query(default=None, max_length=120),
    active_only: bool = True,
    canonical_only: bool = True,
    session: AsyncSession = Depends(get_session),
) -> JobListRead:
    today = datetime.now(KARACHI).date()
    conditions = [JobPosting.trust_version == TRUST_VERSION]
    if active_only:
        conditions.append(JobPosting.is_active.is_(True))
    if canonical_only:
        conditions.append(JobPosting.is_canonical.is_(True))
    if strict_today:
        conditions.extend(
            [
                JobPosting.is_active.is_(True),
                JobPosting.is_canonical.is_(True),
                JobPosting.freshness_grade.in_(("A", "B")),
                JobPosting.published_local_date == today,
                JobPosting.remote_mode == "remote",
                JobPosting.pakistan_eligibility == "yes",
            ]
        )
    if eligibility:
        conditions.append(JobPosting.pakistan_eligibility == eligibility)
    if remote_mode:
        conditions.append(JobPosting.remote_mode == remote_mode)
    if freshness_grade:
        conditions.append(JobPosting.freshness_grade == freshness_grade)
    if gulf_employer is not None:
        conditions.append(JobPosting.employer_headquarters_gcc.is_(gulf_employer))
    if gulf_location is not None:
        conditions.append(JobPosting.job_location_gcc.is_(gulf_location))
    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(
            or_(
                JobPosting.title.ilike(pattern),
                JobPosting.employer_name.ilike(pattern),
                JobPosting.location_text.ilike(pattern),
            )
        )

    total = int(await session.scalar(select(func.count(JobPosting.id)).where(*conditions)) or 0)
    statement = (
        select(JobPosting, SourceRegistry)
        .join(SourceRegistry, SourceRegistry.id == JobPosting.source_registry_id)
        .where(*conditions)
        .order_by(
            JobPosting.published_local_date.desc().nullslast(),
            JobPosting.first_seen_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(statement)).all()
    return JobListRead(
        items=[_job_read(posting, source) for posting, source in rows],
        total=total,
        page=page,
        page_size=page_size,
        strict_today=strict_today,
    )


@router.get("/{job_id}", response_model=JobDetailRead)
async def get_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> JobDetailRead:
    row = (
        await session.execute(
            select(JobPosting, SourceRegistry)
            .join(SourceRegistry, SourceRegistry.id == JobPosting.source_registry_id)
            .where(
                JobPosting.id == job_id,
                JobPosting.trust_version == TRUST_VERSION,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Trusted job not found")
    posting, source = row
    return JobDetailRead(
        **_job_read(posting, source).model_dump(),
        sanitized_description_html=posting.sanitized_description_html,
    )
