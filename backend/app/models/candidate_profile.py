from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.job_match import JobMatch


class CandidateProfile(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (Index("ix_candidate_profiles_current", "is_current"),)

    version: Mapped[int] = mapped_column(Integer, unique=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    resume_filename: Mapped[str] = mapped_column(String(255))
    resume_sha256: Mapped[str] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(200))
    headline: Mapped[str] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Karachi")
    years_experience: Mapped[float] = mapped_column(Float)
    role_families: Mapped[list[str]] = mapped_column(JSONB, default=list)
    seniority_levels: Mapped[list[str]] = mapped_column(JSONB, default=list)
    skills: Mapped[dict[str, list[str]]] = mapped_column(JSONB, default=dict)
    cloud_platforms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    domains: Mapped[list[str]] = mapped_column(JSONB, default=list)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    extraction_evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    matches: Mapped[list[JobMatch]] = relationship(back_populates="profile")
