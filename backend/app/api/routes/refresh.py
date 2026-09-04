from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.common import utc_now
from app.models.refresh_run import RefreshRun
from app.refresh.service import DailyRefreshService
from app.schemas.refresh import RefreshRunRead

router = APIRouter(prefix="/refresh-runs", tags=["refresh"])
ACTIVE_STATUSES = ("queued", "running")
_background_tasks: set[asyncio.Task[None]] = set()


def _schedule_refresh(run_id: UUID) -> None:
    task = asyncio.create_task(DailyRefreshService(run_id).run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


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
        if active.started_at < utc_now() - timedelta(hours=2):
            active.status = "failed"
            active.stage = "completed"
            active.finished_at = utc_now()
            active.error_summary = "Refresh was abandoned after a backend restart or timeout"
            await session.flush()
        else:
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
    return run


@router.get("/{run_id}", response_model=RefreshRunRead)
async def get_refresh(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> RefreshRun:
    run = await session.get(RefreshRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Refresh run not found")
    return run
