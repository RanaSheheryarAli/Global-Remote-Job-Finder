from datetime import timedelta

from app.models.common import utc_now
from app.models.source_registry import SourceRegistry

MIN_REFRESH_INTERVALS = {
    "himalayas": timedelta(hours=24),
    "jobicy": timedelta(hours=1),
    "remotive": timedelta(hours=6),
}


def retry_after_seconds(source: SourceRegistry) -> int | None:
    interval = MIN_REFRESH_INTERVALS.get(source.source_type)
    if interval is None or source.last_success_at is None:
        return None
    remaining = source.last_success_at + interval - utc_now()
    seconds = int(remaining.total_seconds())
    return max(1, seconds) if seconds > 0 else None
