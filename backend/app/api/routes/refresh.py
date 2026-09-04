from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.models.common import utc_now
from app.models.refresh_run import RefreshRun
from app.models.source_run import SourceRun
from app.refresh.service import DailyRefreshService
from app.schemas.refresh import RefreshRunRead

router = APIRouter(prefix="/refresh-runs", tags=["refresh"])
logger = logging.getLogger(__name__)
ACTIVE_STATUSES = ("queued", "running")
_background_tasks: set[asyncio.Task[None]] = set()


def _schedule_refresh(run_id: UUID) -> None:
    task = asyncio.create_task(DailyRefreshService(run_id).run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _expire_stale_run(session: AsyncSession, run: RefreshRun) -> bool:
    if run.status not in ACTIVE_STATUSES:
        return False
    settings = get_settings()
    stale_before = utc_now() - timedelta(seconds=settings.refresh_stale_after_seconds)
    if run.started_at > stale_before:
        return False
    last_source_finish = await session.scalar(
        select(func.max(SourceRun.finished_at)).where(SourceRun.refresh_run_id == run.id)
    )
    last_activity = (
        max(run.started_at, last_source_finish) if last_source_finish else run.started_at
    )
    if last_activity > stale_before:
        return False
    run.status = "failed"
    run.stage = "completed"
    run.finished_at = utc_now()
    run.error_summary = (
        "Refresh stopped because the backend restarted or no source completed within "
        f"{settings.refresh_stale_after_seconds // 60} minutes. You can safely fetch again."
    )
    logger.warning("refresh_marked_stale refresh_run_id=%s", run.id)
    await session.flush()
    return True


@router.post("", response_model=RefreshRunRead, status_code=status.HTTP_202_ACCEPTED)
async def start_refresh(session: AsyncSession = Depends(get_session)) -> RefreshRun:
    # Transaction-scoped PostgreSQL lock makes concurrent button clicks converge on one run.
    await session.execute(text("SELECT pg_advisory_xact_lock(260904)"))
    active = await session.scalar(
        select(RefreshRun)
        .where(RefreshRun.status.in_(ACTIVE_STATUSES))
        .order_by(RefreshRun.started_at.desc())
    )
    if active is not None:
        if not await _expire_stale_run(session, active):
            await session.commit()
            return active
    run = RefreshRun(status="queued", trigger="manual", stage="queued")
    session.add(run)
    await session.commit()
    await session.refresh(run)
    _schedule_refresh(run.id)
    return run


@router.get("/latest", response_model=RefreshRunRead)
async def latest_refresh(session: AsyncSession = Depends(get_session)) -> RefreshRun:
    run = await session.scalar(select(RefreshRun).order_by(RefreshRun.started_at.desc()))
    if run is None:
        raise HTTPException(status_code=404, detail="No refresh has been started")
    if await _expire_stale_run(session, run):
        await session.commit()
    return run


@router.get("/{run_id}", response_model=RefreshRunRead)
async def get_refresh(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> RefreshRun:
    run = await session.get(RefreshRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Refresh run not found")
    if await _expire_stale_run(session, run):
        await session.commit()
    return run
