from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RefreshRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    trigger: str
    stage: str
    started_at: datetime
    finished_at: datetime | None
    sources_total: int
    sources_completed: int
    sources_succeeded: int
    sources_failed: int
    sources_skipped: int
    received_count: int
    new_count: int
    changed_count: int
    unchanged_count: int
    deactivated_count: int
    verified_today_count: int
    worldwide_count: int
    pakistan_eligible_count: int
    unclear_count: int
    matches_scored: int
    strict_matches: int
    uncertain_matches: int
    excluded_matches: int
    failures: list[dict]
    error_summary: str | None
