"""Ingestion relevance gate and additional public job feeds.

Revision ID: 20260908_0006
Revises: 20260904_0005
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260908_0006"
down_revision: str | None = "20260904_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_source_registry_source_type", "source_registry", type_="check")
    op.create_check_constraint(
        "ck_source_registry_source_type",
        "source_registry",
        "source_type IN ('greenhouse', 'lever', 'ashby', 'remoteok', 'himalayas', "
        "'jobicy', 'remotive', 'wwr')",
    )
    op.add_column(
        "job_postings",
        sa.Column("relevance_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "source_runs",
        sa.Column("rejected_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "refresh_runs",
        sa.Column("rejected_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "job_rejections",
        sa.Column("source_registry_id", sa.Uuid(), nullable=False),
        sa.Column("source_job_id", sa.String(200), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("location_text", sa.String(500), nullable=True),
        sa.Column("application_url", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(12), nullable=False),
        sa.Column("role_family", sa.String(40), nullable=True),
        sa.Column(
            "matched_terms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("relevance_version", sa.Integer(), nullable=False),
        sa.Column("first_rejected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_rejected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["source_registry_id"], ["source_registry.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_registry_id", "source_job_id", name="uq_rejection_source_job"),
    )
    op.create_index(
        "ix_job_rejections_source_last_seen",
        "job_rejections",
        ["source_registry_id", "last_rejected_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_rejections_source_last_seen", table_name="job_rejections")
    op.drop_table("job_rejections")
    op.drop_column("refresh_runs", "rejected_count")
    op.drop_column("source_runs", "rejected_count")
    op.drop_column("job_postings", "relevance_version")
    op.drop_constraint("ck_source_registry_source_type", "source_registry", type_="check")
    op.create_check_constraint(
        "ck_source_registry_source_type",
        "source_registry",
        "source_type IN ('greenhouse', 'lever', 'ashby', 'remoteok')",
    )
