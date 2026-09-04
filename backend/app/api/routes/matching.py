from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.jobs import _job_read
from app.core.config import get_settings
from app.db.session import get_session
from app.matching.engine import MATCHER_VERSION
from app.matching.profile import parse_resume_pdf
from app.matching.service import rebuild_profile_matches
from app.models.candidate_profile import CandidateProfile
from app.models.job_match import JobMatch
from app.models.job_posting import JobPosting
from app.models.source_registry import SourceRegistry
from app.schemas.matching import (
    CandidateProfileRead,
    MatchListRead,
    MatchRead,
    MatchRebuildRead,
    MatchSummaryRead,
)

router = APIRouter(tags=["matching"])
KARACHI = ZoneInfo("Asia/Karachi")


def _profile_read(profile: CandidateProfile) -> CandidateProfileRead:
    return CandidateProfileRead(
        id=profile.id,
        version=profile.version,
        is_current=profile.is_current,
        resume_filename=profile.resume_filename,
        resume_sha256=profile.resume_sha256,
        full_name=profile.full_name,
        headline=profile.headline,
        location=profile.location,
        timezone=profile.timezone,
        years_experience=profile.years_experience,
        role_families=profile.role_families,
        seniority_levels=profile.seniority_levels,
        skills=profile.skills,
        cloud_platforms=profile.cloud_platforms,
        domains=profile.domains,
        preferences=profile.preferences,
        extraction_evidence=profile.extraction_evidence,
        created_at=profile.created_at,
    )


async def _current_profile(session: AsyncSession) -> CandidateProfile:
    profile = await session.scalar(
        select(CandidateProfile)
        .where(CandidateProfile.is_current.is_(True))
        .order_by(CandidateProfile.version.desc())
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="No candidate profile has been created")
    return profile


@router.post(
    "/resume",
    response_model=CandidateProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def parse_resume(
    request: Request,
    filename: str = Query(min_length=5, max_length=255),
    session: AsyncSession = Depends(get_session),
) -> CandidateProfileRead:
    settings = get_settings()
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name.casefold().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Filename must be a plain .pdf name")
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/pdf":
        raise HTTPException(status_code=415, detail="Content-Type must be application/pdf")
    data = await request.body()
    if not data or len(data) > settings.resume_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Resume must be between 1 byte and {settings.resume_max_bytes} bytes",
        )
    try:
        parsed = parse_resume_pdf(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    current_version = int(await session.scalar(select(func.max(CandidateProfile.version))) or 0)
    await session.execute(
        update(CandidateProfile)
        .where(CandidateProfile.is_current.is_(True))
        .values(is_current=False)
    )
    facts = parsed.facts
    profile = CandidateProfile(
        version=current_version + 1,
        is_current=True,
        resume_filename=safe_name,
        resume_sha256=parsed.sha256,
        full_name=facts.full_name,
        headline=facts.headline,
        location=facts.location,
        timezone=facts.timezone,
        years_experience=facts.years_experience,
        role_families=facts.role_families,
        seniority_levels=facts.seniority_levels,
        skills=facts.skills,
        cloud_platforms=facts.cloud_platforms,
        domains=facts.domains,
        preferences=facts.preferences,
        extraction_evidence=facts.extraction_evidence,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return _profile_read(profile)


@router.get("/profile", response_model=CandidateProfileRead)
async def get_profile(session: AsyncSession = Depends(get_session)) -> CandidateProfileRead:
    return _profile_read(await _current_profile(session))


@router.post("/matches/rebuild", response_model=MatchRebuildRead)
async def rebuild_matches(
    session: AsyncSession = Depends(get_session),
) -> MatchRebuildRead:
    profile = await _current_profile(session)
    result = await rebuild_profile_matches(session, profile)
    await session.commit()
    return MatchRebuildRead(
        profile_version=result.profile_version,
        matcher_version=result.matcher_version,
        scored=result.scored,
        strict_visible=result.strict_visible,
        uncertain_visible=result.uncertain_visible,
        excluded=result.excluded,
    )


@router.get("/matches/summary", response_model=MatchSummaryRead)
async def match_summary(session: AsyncSession = Depends(get_session)) -> MatchSummaryRead:
    profile = await _current_profile(session)
    base = [
        JobMatch.candidate_profile_id == profile.id,
        JobMatch.matcher_version == MATCHER_VERSION,
    ]

    async def count(*extra: object) -> int:
        return int(await session.scalar(select(func.count(JobMatch.id)).where(*base, *extra)) or 0)

    return MatchSummaryRead(
        profile_version=profile.version,
        matcher_version=MATCHER_VERSION,
        total_scored=await count(),
        strong=await count(JobMatch.score >= 85, JobMatch.uncertain_gate_passed.is_(True)),
        good=await count(
            JobMatch.score >= 70,
            JobMatch.score < 85,
            JobMatch.uncertain_gate_passed.is_(True),
        ),
        possible=await count(
            JobMatch.score >= 55,
            JobMatch.score < 70,
            JobMatch.uncertain_gate_passed.is_(True),
        ),
        strict_visible=await count(
            JobMatch.score >= 55,
            JobMatch.hard_gate_passed.is_(True),
        ),
        uncertain_visible=await count(
            JobMatch.score >= 55,
            JobMatch.hard_gate_passed.is_(False),
            JobMatch.uncertain_gate_passed.is_(True),
        ),
        excluded=await count(
            or_(
                JobMatch.uncertain_gate_passed.is_(False),
                JobMatch.score < 55,
            )
        ),
    )


@router.get("/matches", response_model=MatchListRead)
async def list_matches(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    min_score: int = Query(default=55, ge=0, le=100),
    include_uncertain: bool = False,
    strict_today: bool = False,
    scope: Literal["pakistan", "worldwide", "unclear"] = "pakistan",
    freshness: Literal["verified_today", "newly_discovered"] | None = None,
    refresh_run_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> MatchListRead:
    profile = await _current_profile(session)
    conditions = [
        JobMatch.candidate_profile_id == profile.id,
        JobMatch.matcher_version == MATCHER_VERSION,
        JobMatch.score >= min_score,
        JobPosting.is_active.is_(True),
        JobPosting.is_canonical.is_(True),
    ]
    if scope == "unclear":
        conditions.extend(
            [
                JobMatch.uncertain_gate_passed.is_(True),
                JobMatch.hard_gate_passed.is_(False),
                JobPosting.pakistan_eligibility == "unknown",
            ]
        )
    elif include_uncertain:
        conditions.append(JobMatch.uncertain_gate_passed.is_(True))
    else:
        conditions.append(JobMatch.hard_gate_passed.is_(True))
    if scope == "worldwide":
        conditions.append(JobPosting.global_remote.is_(True))
    if strict_today or freshness == "verified_today":
        conditions.extend(
            [
                JobPosting.freshness_grade.in_(("A", "B")),
                JobPosting.published_local_date == datetime.now(KARACHI).date(),
            ]
        )
    if freshness == "newly_discovered":
        if refresh_run_id is None:
            raise HTTPException(
                status_code=422,
                detail="refresh_run_id is required for newly_discovered matches",
            )
        conditions.append(JobPosting.discovered_refresh_run_id == refresh_run_id)
    elif refresh_run_id is not None:
        conditions.append(
            or_(
                JobPosting.discovered_refresh_run_id == refresh_run_id,
                JobPosting.updated_refresh_run_id == refresh_run_id,
            )
        )

    join = (
        select(JobMatch, JobPosting, SourceRegistry)
        .join(JobPosting, JobPosting.id == JobMatch.job_posting_id)
        .join(SourceRegistry, SourceRegistry.id == JobPosting.source_registry_id)
        .where(*conditions)
    )
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(JobMatch)
            .join(JobPosting, JobPosting.id == JobMatch.job_posting_id)
            .where(*conditions)
        )
        or 0
    )
    rows = (
        await session.execute(
            join.order_by(
                JobMatch.score.desc(),
                JobPosting.published_local_date.desc().nullslast(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [
        MatchRead(
            id=match.id,
            profile_version=profile.version,
            matcher_version=match.matcher_version,
            hard_gate_passed=match.hard_gate_passed,
            uncertain_gate_passed=match.uncertain_gate_passed,
            gate_reasons=match.gate_reasons,
            score=match.score,
            score_label=match.score_label,
            components=match.components,
            matched_skills=match.matched_skills,
            missing_skills=match.missing_skills,
            evidence=match.evidence,
            job=_job_read(job, source),
        )
        for match, job, source in rows
    ]
    return MatchListRead(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        include_uncertain=include_uncertain,
        scope=scope,
        freshness=freshness,
        min_score=min_score,
    )
