"""Phase 4 trust layer fields.

Revision ID: 20260903_0003
Revises: 20260903_0002
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260903_0003"
down_revision: str | None = "20260903_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job_postings", sa.Column("normalized_title", sa.String(500)))
    op.add_column(
        "job_postings",
        sa.Column(
            "structured_locations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("job_postings", sa.Column("sanitized_description_html", sa.Text()))
    op.add_column(
        "job_postings", sa.Column("normalized_employment_type", sa.String(32), nullable=True)
    )
    op.add_column(
        "job_postings",
        sa.Column(
            "normalized_compensation",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "job_postings", sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("job_postings", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "job_postings",
        sa.Column("freshness_grade", sa.String(1), server_default="D", nullable=False),
    )
    op.add_column(
        "job_postings",
        sa.Column("freshness_label", sa.String(120), server_default="Unverified", nullable=False),
    )
    op.add_column("job_postings", sa.Column("published_local_date", sa.Date(), nullable=True))
    op.add_column(
        "job_postings",
        sa.Column("is_reposted", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "job_postings", sa.Column("reposted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "job_postings",
        sa.Column("remote_mode", sa.String(16), server_default="unknown", nullable=False),
    )
    op.add_column(
        "job_postings",
        sa.Column("pakistan_eligibility", sa.String(16), server_default="unknown", nullable=False),
    )
    for name in ("eligibility_positive_evidence", "eligibility_negative_evidence"):
        op.add_column(
            "job_postings",
            sa.Column(
                name,
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
        )
    op.add_column(
        "job_postings",
        sa.Column(
            "employer_headquarters_gcc",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column("job_postings", sa.Column("job_location_gcc", sa.Boolean(), nullable=True))
    op.add_column(
        "job_postings", sa.Column("description_fingerprint", sa.String(64), nullable=True)
    )
    op.add_column("job_postings", sa.Column("dedupe_key", sa.String(64), nullable=True))
    op.add_column(
        "job_postings",
        sa.Column(
            "canonical_job_id",
            sa.Uuid(),
            sa.ForeignKey("job_postings.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "job_postings",
        sa.Column("is_canonical", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "job_postings",
        sa.Column("trust_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.execute(
        "UPDATE job_postings SET normalized_title = lower(title), "
        "sanitized_description_html = description_html, canonical_job_id = id"
    )
    op.execute(
        "UPDATE job_postings SET employer_headquarters_gcc = source_registry.is_gcc "
        "FROM source_registry WHERE job_postings.source_registry_id = source_registry.id"
    )
    op.alter_column("job_postings", "normalized_title", nullable=False)
    op.alter_column("job_postings", "sanitized_description_html", nullable=False)
    op.create_check_constraint(
        "ck_job_freshness", "job_postings", "freshness_grade IN ('A', 'B', 'C', 'D')"
    )
    op.create_check_constraint(
        "ck_job_remote_mode",
        "job_postings",
        "remote_mode IN ('remote', 'hybrid', 'onsite', 'unknown')",
    )
    op.create_check_constraint(
        "ck_job_pakistan_eligibility",
        "job_postings",
        "pakistan_eligibility IN ('yes', 'no', 'unknown')",
    )
    op.create_index("ix_job_postings_dedupe_key", "job_postings", ["dedupe_key"])
    op.create_index(
        "ix_job_postings_strict_feed",
        "job_postings",
        [
            "is_active",
            "is_canonical",
            "freshness_grade",
            "published_local_date",
            "remote_mode",
            "pakistan_eligibility",
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_job_postings_strict_feed", table_name="job_postings")
    op.drop_index("ix_job_postings_dedupe_key", table_name="job_postings")
    op.drop_constraint("ck_job_pakistan_eligibility", "job_postings", type_="check")
    op.drop_constraint("ck_job_remote_mode", "job_postings", type_="check")
    op.drop_constraint("ck_job_freshness", "job_postings", type_="check")
    for column in (
        "trust_version",
        "is_canonical",
        "canonical_job_id",
        "dedupe_key",
        "description_fingerprint",
        "job_location_gcc",
        "employer_headquarters_gcc",
        "eligibility_negative_evidence",
        "eligibility_positive_evidence",
        "pakistan_eligibility",
        "remote_mode",
        "reposted_at",
        "is_reposted",
        "published_local_date",
        "freshness_label",
        "freshness_grade",
        "closed_at",
        "last_verified_at",
        "normalized_compensation",
        "normalized_employment_type",
        "sanitized_description_html",
        "structured_locations",
        "normalized_title",
    ):
        op.drop_column("job_postings", column)
