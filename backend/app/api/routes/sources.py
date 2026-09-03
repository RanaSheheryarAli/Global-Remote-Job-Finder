from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.ingestion.factory import build_source_adapter
from app.ingestion.repository import SqlAlchemyIngestionRepository
from app.ingestion.service import IngestionFailed, IngestionService
from app.ingestion.source_health import mark_source_failure, mark_source_success
from app.models.common import utc_now
from app.models.source_registry import SourceRegistry
from app.models.source_run import SourceRun
from app.registry import load_phase3_sources
from app.schemas.source import (
    IngestionReportRead,
    SeedResultRead,
    SourceCreate,
    SourceHealthSummary,
    SourceRead,
    SourceValidationRead,
)

router = APIRouter(prefix="/sources", tags=["sources"])


def source_from_payload(payload: SourceCreate) -> SourceRegistry:
    return SourceRegistry(
        name=payload.name,
        source_type=payload.source_type,
        board_token=payload.board_token,
        company_domain=payload.company_domain,
        career_url=str(payload.career_url) if payload.career_url else None,
        provider_region=payload.provider_region,
        headquarters_country=payload.headquarters_country,
        is_gcc=payload.is_gcc,
        is_aggregator=payload.is_aggregator,
        requires_attribution=payload.requires_attribution,
        attribution_name=payload.attribution_name,
        attribution_url=str(payload.attribution_url) if payload.attribution_url else None,
    )


async def get_source_or_404(session: AsyncSession, source_id: UUID) -> SourceRegistry:
    source = await session.get(SourceRegistry, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.get("", response_model=list[SourceRead])
async def list_sources(session: AsyncSession = Depends(get_session)) -> list[SourceRegistry]:
    result = await session.scalars(
        select(SourceRegistry).order_by(SourceRegistry.source_type, SourceRegistry.name)
    )
    return list(result)


@router.get("/health", response_model=SourceHealthSummary)
async def source_health(session: AsyncSession = Depends(get_session)) -> SourceHealthSummary:
    sources = list(
        await session.scalars(
            select(SourceRegistry).order_by(SourceRegistry.source_type, SourceRegistry.name)
        )
    )
    now = utc_now()
    return SourceHealthSummary(
        total=len(sources),
        enabled=sum(source.enabled for source in sources),
        healthy=sum(source.health_status == "healthy" for source in sources),
        degraded=sum(source.health_status == "degraded" for source in sources),
        failing=sum(source.health_status == "failing" for source in sources),
        unknown=sum(source.health_status == "unknown" for source in sources),
        circuits_open=sum(
            source.circuit_open_until is not None and source.circuit_open_until > now
            for source in sources
        ),
        sources=[SourceRead.model_validate(source) for source in sources],
    )


@router.post("/seed/phase-3", response_model=SeedResultRead)
async def seed_phase3_registry(
    session: AsyncSession = Depends(get_session),
) -> SeedResultRead:
    definitions = [SourceCreate.model_validate(item) for item in load_phase3_sources()]
    result = await session.execute(select(SourceRegistry.source_type, SourceRegistry.board_token))
    existing_pairs = set(result.tuples().all())
    created = 0
    for definition in definitions:
        key = (definition.source_type, definition.board_token)
        if key in existing_pairs:
            continue
        session.add(source_from_payload(definition))
        existing_pairs.add(key)
        created += 1
    await session.commit()
    return SeedResultRead(
        created=created,
        existing=len(definitions) - created,
        total_definitions=len(definitions),
    )


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    session: AsyncSession = Depends(get_session),
) -> SourceRegistry:
    source = source_from_payload(payload)
    session.add(source)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="This provider identifier is already registered",
        ) from exc
    await session.refresh(source)
    return source


@router.post("/{source_id}/validate", response_model=SourceValidationRead)
async def validate_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> SourceValidationRead:
    source = await get_source_or_404(session, source_id)
    settings = get_settings()
    adapter = build_source_adapter(source, settings)
    try:
        summaries = await adapter.list_jobs()
        if not summaries:
            raise ValueError("Source returned no currently published jobs")
        sample = await adapter.fetch_and_normalize(summaries[0])
        sample_url = sample.source_url or sample.application_url
        mark_source_success(source, job_count=len(summaries), sample_url=sample_url)
        await session.commit()
    except Exception as exc:
        mark_source_failure(
            source,
            error=str(exc),
            threshold=settings.source_circuit_breaker_threshold,
            cooldown_minutes=settings.source_circuit_breaker_cooldown_minutes,
        )
        await session.commit()
        raise HTTPException(status_code=502, detail=f"Source validation failed: {exc}") from exc
    finally:
        await adapter.close()
    if source.validated_at is None:
        raise HTTPException(status_code=500, detail="Source validation timestamp was not recorded")
    return SourceValidationRead(
        source_id=source.id,
        source_type=source.source_type,
        job_count=len(summaries),
        sample_url=sample_url,
        health_status=source.health_status,
        validated_at=source.validated_at,
    )


@router.post("/{source_id}/ingest", response_model=IngestionReportRead)
async def ingest_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> IngestionReportRead:
    source = await get_source_or_404(session, source_id)
    if not source.enabled:
        raise HTTPException(status_code=409, detail="Source is disabled")
    now = utc_now()
    if source.circuit_open_until and source.circuit_open_until > now:
        raise HTTPException(
            status_code=429,
            detail=f"Source circuit is open until {source.circuit_open_until.isoformat()}",
        )

    settings = get_settings()
    adapter = build_source_adapter(source, settings)
    repository = SqlAlchemyIngestionRepository(session)
    service = IngestionService(source=source, adapter=adapter, repository=repository)
    try:
        report = await service.run()
        await session.commit()
    except IngestionFailed as exc:
        # Keep canonical jobs atomic: a failed board run must not expose a partial refresh.
        await session.rollback()
        source = await get_source_or_404(session, source_id)
        mark_source_failure(
            source,
            error=str(exc),
            threshold=settings.source_circuit_breaker_threshold,
            cooldown_minutes=settings.source_circuit_breaker_cooldown_minutes,
        )
        session.add(
            SourceRun(
                source=source,
                status="failed",
                finished_at=utc_now(),
                error_summary=str(exc)[:4000],
            )
        )
        await session.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await adapter.close()
    return IngestionReportRead(
        source_id=report.source_id,
        run_id=report.run_id,
        received_count=report.received_count,
        new_count=report.new_count,
        changed_count=report.changed_count,
        unchanged_count=report.unchanged_count,
        deactivated_count=report.deactivated_count,
    )
