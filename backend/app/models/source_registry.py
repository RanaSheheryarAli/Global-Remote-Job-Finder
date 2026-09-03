from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.job_posting import JobPosting
    from app.models.source_run import SourceRun


class SourceRegistry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_registry"
    __table_args__ = (
        UniqueConstraint("source_type", "board_token", name="uq_source_type_board_token"),
        CheckConstraint(
            "source_type IN ('greenhouse', 'lever', 'ashby', 'remoteok')",
            name="ck_source_registry_source_type",
        ),
        CheckConstraint(
            "provider_region IN ('global', 'eu')",
            name="ck_source_registry_provider_region",
        ),
        CheckConstraint(
            "health_status IN ('unknown', 'healthy', 'degraded', 'failing', 'disabled')",
            name="ck_source_registry_health_status",
        ),
    )

    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(32), default="greenhouse")
    board_token: Mapped[str] = mapped_column(String(160))
    company_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    career_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_region: Mapped[str] = mapped_column(String(16), default="global")
    headquarters_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_gcc: Mapped[bool] = mapped_column(Boolean, default=False)
    is_aggregator: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_attribution: Mapped[bool] = mapped_column(Boolean, default=False)
    attribution_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attribution_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health_status: Mapped[str] = mapped_column(String(32), default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    circuit_open_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_job_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_sample_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    runs: Mapped[list["SourceRun"]] = relationship(back_populates="source")
    postings: Mapped[list["JobPosting"]] = relationship(back_populates="source")
