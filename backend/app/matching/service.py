from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.matching.engine import MATCHER_VERSION, candidate_facts_from_record, score_job
from app.models.candidate_profile import CandidateProfile
from app.models.job_match import JobMatch
from app.models.job_posting import JobPosting
from app.trust.engine import TRUST_VERSION

KARACHI = ZoneInfo("Asia/Karachi")


@dataclass(frozen=True, slots=True)
class RebuildResult:
    profile_version: int
    matcher_version: int
    scored: int
    strict_visible: int
    uncertain_visible: int
    excluded: int


async def rebuild_profile_matches(
    session: AsyncSession,
    profile: CandidateProfile,
) -> RebuildResult:
    facts = candidate_facts_from_record(profile)
    jobs = list(
        await session.scalars(
            select(JobPosting).where(
                JobPosting.is_active.is_(True),
                JobPosting.is_canonical.is_(True),
                JobPosting.trust_version == TRUST_VERSION,
            )
        )
    )
    existing = {
        match.job_posting_id: match
        for match in await session.scalars(
            select(JobMatch).where(
                JobMatch.candidate_profile_id == profile.id,
                JobMatch.matcher_version == MATCHER_VERSION,
            )
        )
    }
    strict_visible = 0
    uncertain_visible = 0
    excluded = 0
    now = datetime.now(KARACHI)
    for job in jobs:
        result = score_job(job, facts, now=now)
        match = existing.get(job.id)
        if match is None:
            match = JobMatch(
                candidate_profile_id=profile.id,
                job_posting_id=job.id,
                matcher_version=MATCHER_VERSION,
                score=result.score,
                score_label=result.score_label,
            )
            session.add(match)
        match.hard_gate_passed = result.hard_gate_passed
        match.uncertain_gate_passed = result.uncertain_gate_passed
        match.gate_reasons = result.gate_reasons
        match.score = result.score
        match.score_label = result.score_label
        match.components = result.components
        match.matched_skills = result.matched_skills
        match.missing_skills = result.missing_skills
        match.evidence = result.evidence
        if result.hard_gate_passed and result.score >= 55:
            strict_visible += 1
        elif result.uncertain_gate_passed and result.score >= 55:
            uncertain_visible += 1
        else:
            excluded += 1
    await session.flush()
    return RebuildResult(
        profile_version=profile.version,
        matcher_version=MATCHER_VERSION,
        scored=len(jobs),
        strict_visible=strict_visible,
        uncertain_visible=uncertain_visible,
        excluded=excluded,
    )
