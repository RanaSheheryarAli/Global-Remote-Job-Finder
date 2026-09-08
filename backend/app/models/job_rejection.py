from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.source_registry import SourceRegistry


class JobRejection(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_rejections"
    __table_args__ = (
        UniqueConstraint("source_registry_id", "source_job_id", name="uq_rejection_source_job"),
        Index("ix_job_rejections_source_last_seen", "source_registry_id", "last_rejected_at"),
    )

    source_registry_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_registry.id", ondelete="CASCADE")
    )
    source_job_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(500))
    location_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    application_url: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(12))
    role_family: Mapped[str | None] = mapped_column(String(40), nullable=True)
    matched_terms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    relevance_version: Mapped[int] = mapped_column(Integer)
    first_rejected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_rejected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    source: Mapped["SourceRegistry"] = relationship()
