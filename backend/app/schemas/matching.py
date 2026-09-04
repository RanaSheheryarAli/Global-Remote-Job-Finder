from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.job import JobRead


class CandidateProfileRead(BaseModel):
    id: UUID
    version: int
    is_current: bool
    resume_filename: str
    resume_sha256: str
    full_name: str
    headline: str
    location: str | None
    timezone: str
    years_experience: float
    role_families: list[str]
    seniority_levels: list[str]
    skills: dict[str, list[str]]
    cloud_platforms: list[str]
    domains: list[str]
    preferences: dict[str, Any]
    extraction_evidence: dict[str, Any]
    created_at: datetime


class MatchRead(BaseModel):
    id: UUID
    profile_version: int
    matcher_version: int
    hard_gate_passed: bool
    uncertain_gate_passed: bool
    gate_reasons: list[str]
    score: int
    score_label: str
    components: dict[str, int]
    matched_skills: list[str]
    missing_skills: list[str]
    evidence: dict[str, Any]
    job: JobRead


class MatchListRead(BaseModel):
    items: list[MatchRead]
    total: int
    page: int
    page_size: int
    include_uncertain: bool
    scope: str
    freshness: str | None
    min_score: int


class MatchRebuildRead(BaseModel):
    profile_version: int
    matcher_version: int
    scored: int
    strict_visible: int
    uncertain_visible: int
    excluded: int


class MatchSummaryRead(BaseModel):
    profile_version: int
    matcher_version: int
    total_scored: int
    strong: int
    good: int
    possible: int
    strict_visible: int
    uncertain_visible: int
    excluded: int
