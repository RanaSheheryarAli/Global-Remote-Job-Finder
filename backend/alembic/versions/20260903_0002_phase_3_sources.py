"""Phase 3 source expansion and health fields.

Revision ID: 20260903_0002
Revises: 20260903_0001
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260903_0002"
down_revision: str | None = "20260903_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_source_registry_source_type",
        "source_registry",
        "source_type IN ('greenhouse', 'lever', 'ashby', 'remoteok')",
    )
    op.add_column("source_registry", sa.Column("career_url", sa.Text(), nullable=True))
    op.add_column(
        "source_registry",
        sa.Column("provider_region", sa.String(length=16), server_default="global", nullable=False),
    )
    op.add_column(
        "source_registry",
        sa.Column("is_aggregator", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "source_registry",
        sa.Column("requires_attribution", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "source_registry", sa.Column("attribution_name", sa.String(length=100), nullable=True)
    )
    op.add_column("source_registry", sa.Column("attribution_url", sa.Text(), nullable=True))
    op.add_column(
        "source_registry",
        sa.Column("health_status", sa.String(length=32), server_default="unknown", nullable=False),
    )
    op.add_column(
        "source_registry", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "source_registry", sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "source_registry",
        sa.Column("circuit_open_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "source_registry",
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("source_registry", sa.Column("last_job_count", sa.Integer(), nullable=True))
    op.add_column("source_registry", sa.Column("last_error_summary", sa.Text(), nullable=True))
    op.add_column(
        "source_registry", sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("source_registry", sa.Column("validation_sample_url", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_source_registry_provider_region",
        "source_registry",
        "provider_region IN ('global', 'eu')",
    )
    op.create_check_constraint(
        "ck_source_registry_health_status",
        "source_registry",
        "health_status IN ('unknown', 'healthy', 'degraded', 'failing', 'disabled')",
    )

    op.add_column("job_postings", sa.Column("employer_name", sa.String(length=300), nullable=True))
    op.add_column("job_postings", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("job_postings", sa.Column("workplace_type", sa.String(length=32), nullable=True))
    op.add_column("job_postings", sa.Column("employment_type", sa.String(length=80), nullable=True))
    op.add_column(
        "job_postings",
        sa.Column("compensation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "job_postings", sa.Column("attribution_name", sa.String(length=100), nullable=True)
    )
    op.add_column("job_postings", sa.Column("attribution_url", sa.Text(), nullable=True))
    op.execute(
        "UPDATE job_postings SET employer_name = source_registry.name, "
        "source_url = job_postings.application_url FROM source_registry "
        "WHERE job_postings.source_registry_id = source_registry.id"
    )
    op.alter_column("job_postings", "employer_name", nullable=False)
    op.alter_column("job_postings", "source_url", nullable=False)


def downgrade() -> None:
    op.drop_constraint("ck_source_registry_health_status", "source_registry", type_="check")
    op.drop_constraint("ck_source_registry_provider_region", "source_registry", type_="check")
    op.drop_constraint("ck_source_registry_source_type", "source_registry", type_="check")
    for column in (
        "attribution_url",
        "attribution_name",
        "compensation",
        "employment_type",
        "workplace_type",
        "source_url",
        "employer_name",
    ):
        op.drop_column("job_postings", column)
    for column in (
        "validation_sample_url",
        "validated_at",
        "last_error_summary",
        "last_job_count",
        "consecutive_failures",
        "circuit_open_until",
        "last_failure_at",
        "last_checked_at",
        "health_status",
        "attribution_url",
        "attribution_name",
        "requires_attribution",
        "is_aggregator",
        "provider_region",
        "career_url",
    ):
        op.drop_column("source_registry", column)
