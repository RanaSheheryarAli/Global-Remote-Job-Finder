"""Phase 6 daily refresh and geographic scope.

Revision ID: 20260904_0005
Revises: 20260904_0004
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260904_0005"
down_revision: str | None = "20260904_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def json_list_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'[]'::jsonb"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "refresh_runs",
        sa.Column("status", sa.String(40), server_default="queued", nullable=False),
        sa.Column("trigger", sa.String(20), server_default="manual", nullable=False),
        sa.Column("stage", sa.String(40), server_default="queued", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *[
            sa.Column(name, sa.Integer(), server_default="0", nullable=False)
            for name in (
                "sources_total",
                "sources_completed",
                "sources_succeeded",
                "sources_failed",
                "sources_skipped",
                "received_count",
                "new_count",
                "changed_count",
                "unchanged_count",
                "deactivated_count",
                "verified_today_count",
                "worldwide_count",
                "pakistan_eligible_count",
                "unclear_count",
                "matches_scored",
                "strict_matches",
                "uncertain_matches",
                "excluded_matches",
            )
        ],
        json_list_column("failures"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'completed_with_errors', "
            "'completed_without_matching', 'failed')",
            name="ck_refresh_run_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_refresh_runs_status_started", "refresh_runs", ["status", "started_at"]
    )
    op.add_column(
        "source_runs",
        sa.Column(
            "refresh_run_id",
            sa.Uuid(),
            sa.ForeignKey("refresh_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_source_runs_refresh_run", "source_runs", ["refresh_run_id"])

    op.add_column(
        "job_postings",
        sa.Column("geographic_scope", sa.String(24), server_default="unknown", nullable=False),
    )
    for name in (
        "allowed_country_codes",
        "excluded_country_codes",
        "allowed_regions",
        "timezone_constraints",
        "geographic_positive_evidence",
        "geographic_restrictive_evidence",
        "geographic_conflicting_evidence",
    ):
        op.add_column("job_postings", json_list_column(name))
    for name in ("residency_required", "work_authorization_required", "global_remote"):
        op.add_column(
            "job_postings",
            sa.Column(name, sa.Boolean(), server_default=sa.false(), nullable=False),
        )
    op.add_column(
        "job_postings",
        sa.Column("eligibility_confidence", sa.String(12), server_default="low", nullable=False),
    )
    for name in ("discovered_refresh_run_id", "updated_refresh_run_id"):
        op.add_column(
            "job_postings",
            sa.Column(
                name,
                sa.Uuid(),
                sa.ForeignKey("refresh_runs.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(f"ix_job_postings_{name}", "job_postings", [name])
    op.create_check_constraint(
        "ck_job_geographic_scope",
        "job_postings",
        "geographic_scope IN ('worldwide', 'country_list', 'region', "
        "'single_country', 'unknown')",
    )
    op.create_check_constraint(
        "ck_job_eligibility_confidence",
        "job_postings",
        "eligibility_confidence IN ('high', 'medium', 'low')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_job_eligibility_confidence", "job_postings", type_="check")
    op.drop_constraint("ck_job_geographic_scope", "job_postings", type_="check")
    for name in ("updated_refresh_run_id", "discovered_refresh_run_id"):
        op.drop_index(f"ix_job_postings_{name}", table_name="job_postings")
        op.drop_column("job_postings", name)
    for name in (
        "eligibility_confidence",
        "global_remote",
        "work_authorization_required",
        "residency_required",
        "geographic_conflicting_evidence",
        "geographic_restrictive_evidence",
        "geographic_positive_evidence",
        "timezone_constraints",
        "allowed_regions",
        "excluded_country_codes",
        "allowed_country_codes",
        "geographic_scope",
    ):
        op.drop_column("job_postings", name)
    op.drop_index("ix_source_runs_refresh_run", table_name="source_runs")
    op.drop_column("source_runs", "refresh_run_id")
    op.drop_index("ix_refresh_runs_status_started", table_name="refresh_runs")
    op.drop_table("refresh_runs")
