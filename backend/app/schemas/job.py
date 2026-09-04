from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

FreshnessGrade = Literal["A", "B", "C", "D"]
RemoteMode = Literal["remote", "hybrid", "onsite", "unknown"]
PakistanEligibility = Literal["yes", "no", "unknown"]
GeographicScope = Literal["worldwide", "country_list", "region", "single_country", "unknown"]


class JobRead(BaseModel):
    id: UUID
    canonical_job_id: UUID | None
    source_name: str
    source_type: str
    source_job_id: str
    employer_name: str
    title: str
    normalized_title: str
    location_text: str | None
    structured_locations: list[dict[str, Any]]
    description_excerpt: str
    source_url: str
    application_url: str
    normalized_employment_type: str | None
    normalized_compensation: dict[str, Any] | None
    attribution_name: str | None
    attribution_url: str | None
    first_published_at: datetime | None
    source_updated_at: datetime | None
    first_seen_at: datetime
    last_verified_at: datetime | None
    freshness_grade: FreshnessGrade
    freshness_label: str
    published_local_date: date | None
    is_reposted: bool
    remote_mode: RemoteMode
    pakistan_eligibility: PakistanEligibility
    eligibility_positive_evidence: list[str]
    eligibility_negative_evidence: list[str]
    geographic_scope: GeographicScope
    allowed_country_codes: list[str]
    excluded_country_codes: list[str]
    allowed_regions: list[str]
    residency_required: bool
    work_authorization_required: bool
    timezone_constraints: list[str]
    global_remote: bool
    eligibility_confidence: Literal["high", "medium", "low"]
    geographic_positive_evidence: list[str]
    geographic_restrictive_evidence: list[str]
    geographic_conflicting_evidence: list[str]
    discovered_refresh_run_id: UUID | None
    updated_refresh_run_id: UUID | None
    employer_headquarters_gcc: bool
    job_location_gcc: bool | None
    is_active: bool


class JobDetailRead(JobRead):
    sanitized_description_html: str


class JobListRead(BaseModel):
    items: list[JobRead]
    total: int
    page: int
    page_size: int
    strict_today: bool
    timezone: str = "Asia/Karachi"


class JobTrustSummary(BaseModel):
    local_date: date
    timezone: str = "Asia/Karachi"
    trusted_active: int
    canonical_active: int
    strict_today: int
    pakistan_yes: int
    pakistan_unknown: int
    worldwide: int
    freshness: dict[str, int]
