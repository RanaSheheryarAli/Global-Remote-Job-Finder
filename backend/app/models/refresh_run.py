from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import UUIDPrimaryKeyMixin, utc_now


class RefreshRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "refresh_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'completed_with_errors', "
            "'completed_without_matching', 'failed')",
            name="ck_refresh_run_status",
        ),
        Index("ix_refresh_runs_status_started", "status", "started_at"),
    )

    status: Mapped[str] = mapped_column(String(40), default="queued")
    trigger: Mapped[str] = mapped_column(String(20), default="manual")
    stage: Mapped[str] = mapped_column(String(40), default="queued")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sources_total: Mapped[int] = mapped_column(Integer, default=0)
    sources_completed: Mapped[int] = mapped_column(Integer, default=0)
    sources_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    sources_failed: Mapped[int] = mapped_column(Integer, default=0)
    sources_skipped: Mapped[int] = mapped_column(Integer, default=0)
    received_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    changed_count: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    deactivated_count: Mapped[int] = mapped_column(Integer, default=0)
    verified_today_count: Mapped[int] = mapped_column(Integer, default=0)
    worldwide_count: Mapped[int] = mapped_column(Integer, default=0)
    pakistan_eligible_count: Mapped[int] = mapped_column(Integer, default=0)
    unclear_count: Mapped[int] = mapped_column(Integer, default=0)
    matches_scored: Mapped[int] = mapped_column(Integer, default=0)
    strict_matches: Mapped[int] = mapped_column(Integer, default=0)
    uncertain_matches: Mapped[int] = mapped_column(Integer, default=0)
    excluded_matches: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
