from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.refresh_run import RefreshRun
    from app.models.source_registry import SourceRegistry


class SourceRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "source_runs"
    __table_args__ = (Index("ix_source_runs_source_started", "source_registry_id", "started_at"),)

    source_registry_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_registry.id", ondelete="CASCADE")
    )
    refresh_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("refresh_runs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    changed_count: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    deactivated_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped["SourceRegistry"] = relationship(back_populates="runs")
    refresh_run: Mapped["RefreshRun | None"] = relationship()
