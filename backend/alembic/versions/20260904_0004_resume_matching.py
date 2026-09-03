"""Phase 5 candidate profile and reproducible job matching.

Revision ID: 20260904_0004
Revises: 20260903_0003
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260904_0004"
down_revision: str | None = "20260903_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_profiles",
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("resume_filename", sa.String(255), nullable=False),
        sa.Column("resume_sha256", sa.String(64), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("headline", sa.String(300), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("years_experience", sa.Float(), nullable=False),
        sa.Column(
            "role_families",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "seniority_levels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "cloud_platforms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "domains",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "extraction_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )
    op.create_index(
        "ix_candidate_profiles_current",
        "candidate_profiles",
        ["is_current"],
    )
    op.create_table(
        "job_matches",
        sa.Column("candidate_profile_id", sa.Uuid(), nullable=False),
        sa.Column("job_posting_id", sa.Uuid(), nullable=False),
        sa.Column("matcher_version", sa.Integer(), nullable=False),
        sa.Column("hard_gate_passed", sa.Boolean(), nullable=False),
        sa.Column("uncertain_gate_passed", sa.Boolean(), nullable=False),
        sa.Column(
            "gate_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("score_label", sa.String(32), nullable=False),
        sa.Column(
            "components",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "matched_skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "missing_skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="ck_job_match_score"),
        sa.ForeignKeyConstraint(
            ["candidate_profile_id"],
            ["candidate_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_posting_id"],
            ["job_postings.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_profile_id",
            "job_posting_id",
            "matcher_version",
            name="uq_job_match_profile_job_version",
        ),
    )
    op.create_index(
        "ix_job_matches_ranked",
        "job_matches",
        ["candidate_profile_id", "hard_gate_passed", "score"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_matches_ranked", table_name="job_matches")
    op.drop_table("job_matches")
    op.drop_index("ix_candidate_profiles_current", table_name="candidate_profiles")
    op.drop_table("candidate_profiles")
