from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.job_snapshot import JobSnapshot
    from app.models.source_registry import SourceRegistry


class JobPosting(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_postings"
    __table_args__ = (
        UniqueConstraint("source_registry_id", "source_job_id", name="uq_posting_source_job"),
        Index("ix_job_postings_active", "source_registry_id", "is_active"),
        Index(
            "ix_job_postings_strict_feed",
            "is_active",
            "is_canonical",
            "freshness_grade",
            "published_local_date",
            "remote_mode",
            "pakistan_eligibility",
        ),
        Index("ix_job_postings_dedupe_key", "dedupe_key"),
        CheckConstraint("freshness_grade IN ('A', 'B', 'C', 'D')", name="ck_job_freshness"),
        CheckConstraint(
            "remote_mode IN ('remote', 'hybrid', 'onsite', 'unknown')",
            name="ck_job_remote_mode",
        ),
        CheckConstraint(
            "pakistan_eligibility IN ('yes', 'no', 'unknown')",
            name="ck_job_pakistan_eligibility",
        ),
        CheckConstraint(
            "geographic_scope IN ('worldwide', 'country_list', 'region', "
            "'single_country', 'unknown')",
            name="ck_job_geographic_scope",
        ),
        CheckConstraint(
            "eligibility_confidence IN ('high', 'medium', 'low')",
            name="ck_job_eligibility_confidence",
        ),
    )

    source_registry_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_registry.id", ondelete="CASCADE")
    )
    source_job_id: Mapped[str] = mapped_column(String(100))
    employer_name: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(500))
    normalized_title: Mapped[str] = mapped_column(String(500))
    location_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    structured_locations: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    description_html: Mapped[str] = mapped_column(Text, default="")
    sanitized_description_html: Mapped[str] = mapped_column(Text, default="")
    description_text: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text)
    application_url: Mapped[str] = mapped_column(Text)
    workplace_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    normalized_employment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    compensation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    normalized_compensation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attribution_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attribution_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness_grade: Mapped[str] = mapped_column(String(1), default="D")
    freshness_label: Mapped[str] = mapped_column(String(120), default="Unverified")
    published_local_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_reposted: Mapped[bool] = mapped_column(Boolean, default=False)
    reposted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remote_mode: Mapped[str] = mapped_column(String(16), default="unknown")
    pakistan_eligibility: Mapped[str] = mapped_column(String(16), default="unknown")
    eligibility_positive_evidence: Mapped[list[str]] = mapped_column(JSONB, default=list)
    eligibility_negative_evidence: Mapped[list[str]] = mapped_column(JSONB, default=list)
    geographic_scope: Mapped[str] = mapped_column(String(24), default="unknown")
    allowed_country_codes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    excluded_country_codes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    allowed_regions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    residency_required: Mapped[bool] = mapped_column(Boolean, default=False)
    work_authorization_required: Mapped[bool] = mapped_column(Boolean, default=False)
    timezone_constraints: Mapped[list[str]] = mapped_column(JSONB, default=list)
    global_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    eligibility_confidence: Mapped[str] = mapped_column(String(12), default="low")
    geographic_positive_evidence: Mapped[list[str]] = mapped_column(JSONB, default=list)
    geographic_restrictive_evidence: Mapped[list[str]] = mapped_column(JSONB, default=list)
    geographic_conflicting_evidence: Mapped[list[str]] = mapped_column(JSONB, default=list)
    discovered_refresh_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("refresh_runs.id", ondelete="SET NULL"), nullable=True
    )
    updated_refresh_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("refresh_runs.id", ondelete="SET NULL"), nullable=True
    )
    employer_headquarters_gcc: Mapped[bool] = mapped_column(Boolean, default=False)
    job_location_gcc: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    description_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    canonical_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_postings.id", ondelete="SET NULL"), nullable=True
    )
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=True)
    trust_version: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    current_content_hash: Mapped[str] = mapped_column(String(64))

    source: Mapped["SourceRegistry"] = relationship(back_populates="postings")
    snapshots: Mapped[list["JobSnapshot"]] = relationship(back_populates="job")
