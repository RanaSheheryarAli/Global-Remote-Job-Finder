from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.job_posting import JobPosting


class JobSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_snapshots"
    __table_args__ = (
        UniqueConstraint("job_posting_id", "content_hash", name="uq_snapshot_job_hash"),
    )

    job_posting_id: Mapped[UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    content_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    job: Mapped["JobPosting"] = relationship(back_populates="snapshots")
