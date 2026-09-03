from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.candidate_profile import CandidateProfile
    from app.models.job_posting import JobPosting


class JobMatch(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint(
            "candidate_profile_id",
            "job_posting_id",
            "matcher_version",
            name="uq_job_match_profile_job_version",
        ),
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_job_match_score"),
        Index(
            "ix_job_matches_ranked",
            "candidate_profile_id",
            "hard_gate_passed",
            "score",
        ),
    )

    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    job_posting_id: Mapped[UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    matcher_version: Mapped[int] = mapped_column(Integer)
    hard_gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    uncertain_gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    gate_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    score: Mapped[int] = mapped_column(Integer)
    score_label: Mapped[str] = mapped_column(String(32))
    components: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    matched_skills: Mapped[list[str]] = mapped_column(JSONB, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(JSONB, default=list)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    profile: Mapped[CandidateProfile] = relationship(back_populates="matches")
    job: Mapped[JobPosting] = relationship()
