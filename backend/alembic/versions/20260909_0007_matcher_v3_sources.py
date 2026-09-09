"""Matcher V3 source and company-diversity support.

Revision ID: 20260909_0007
Revises: 20260908_0006
Create Date: 2026-09-09
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision: str = "20260909_0007"
down_revision: str | None = "20260908_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_source_registry_source_type", "source_registry", type_="check")
    op.create_check_constraint(
        "ck_source_registry_source_type",
        "source_registry",
        "source_type IN ('greenhouse', 'lever', 'ashby', 'remoteok', 'himalayas', "
        "'jobicy', 'remotive', 'wwr', 'smartrecruiters')",
    )
    op.create_index("ix_job_postings_employer_name", "job_postings", ["employer_name"])
    sources = sa.table(
        "source_registry",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("source_type", sa.String()),
        sa.column("board_token", sa.String()),
        sa.column("company_domain", sa.String()),
        sa.column("career_url", sa.Text()),
        sa.column("provider_region", sa.String()),
        sa.column("headquarters_country", sa.String()),
        sa.column("is_gcc", sa.Boolean()),
        sa.column("is_aggregator", sa.Boolean()),
        sa.column("requires_attribution", sa.Boolean()),
    )
    op.bulk_insert(
        sources,
        [
            {
                "id": UUID("7dd0ef04-b3a2-45dd-8047-59b89adae201"),
                "name": "Software Mind",
                "source_type": "smartrecruiters",
                "board_token": "SoftwareMind",
                "company_domain": "softwaremind.com",
                "career_url": "https://jobs.smartrecruiters.com/SoftwareMind",
                "provider_region": "global",
                "headquarters_country": "PL",
                "is_gcc": False,
                "is_aggregator": False,
                "requires_attribution": False,
            },
            {
                "id": UUID("5b721bec-e24d-4d17-a521-a541c5426f54"),
                "name": "Cint",
                "source_type": "smartrecruiters",
                "board_token": "Cint",
                "company_domain": "cint.com",
                "career_url": "https://jobs.smartrecruiters.com/Cint",
                "provider_region": "global",
                "headquarters_country": "SE",
                "is_gcc": False,
                "is_aggregator": False,
                "requires_attribution": False,
            },
            {
                "id": UUID("05999657-a5b3-4719-8ede-fbe6f35c91d2"),
                "name": "ServiceNow",
                "source_type": "smartrecruiters",
                "board_token": "ServiceNow",
                "company_domain": "servicenow.com",
                "career_url": "https://jobs.smartrecruiters.com/ServiceNow",
                "provider_region": "global",
                "headquarters_country": "US",
                "is_gcc": False,
                "is_aggregator": False,
                "requires_attribution": False,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_job_postings_employer_name", table_name="job_postings")
    op.execute("DELETE FROM source_registry WHERE source_type = 'smartrecruiters'")
    op.drop_constraint("ck_source_registry_source_type", "source_registry", type_="check")
    op.create_check_constraint(
        "ck_source_registry_source_type",
        "source_registry",
        "source_type IN ('greenhouse', 'lever', 'ashby', 'remoteok', 'himalayas', "
        "'jobicy', 'remotive', 'wwr')",
    )
