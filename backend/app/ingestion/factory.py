from app.core.config import Settings
from app.ingestion.ashby import AshbyAdapter
from app.ingestion.contracts import SourceAdapter
from app.ingestion.greenhouse import GreenhouseAdapter
from app.ingestion.himalayas import HimalayasAdapter
from app.ingestion.jobicy import JobicyAdapter
from app.ingestion.lever import LeverAdapter
from app.ingestion.remoteok import RemoteOkAdapter
from app.ingestion.remotive import RemotiveAdapter
from app.ingestion.smartrecruiters import SmartRecruitersAdapter
from app.ingestion.wwr import WeWorkRemotelyAdapter
from app.models.source_registry import SourceRegistry


def build_source_adapter(source: SourceRegistry, settings: Settings) -> SourceAdapter:
    common = {
        "timeout_seconds": settings.greenhouse_request_timeout_seconds,
        "max_retries": settings.greenhouse_max_retries,
    }
    if source.source_type == "greenhouse":
        return GreenhouseAdapter(
            source.board_token,
            company_name=source.name,
            **common,
        )
    if source.source_type == "lever":
        return LeverAdapter(
            source.board_token,
            company_name=source.name,
            region=source.provider_region,
            **common,
        )
    if source.source_type == "ashby":
        return AshbyAdapter(
            source.board_token,
            company_name=source.name,
            **common,
        )
    if source.source_type == "smartrecruiters":
        return SmartRecruitersAdapter(
            source.board_token,
            company_name=source.name,
            **common,
        )
    if source.source_type == "remoteok":
        return RemoteOkAdapter(**common)
    if source.source_type == "himalayas":
        return HimalayasAdapter(**common)
    if source.source_type == "jobicy":
        return JobicyAdapter(**common)
    if source.source_type == "remotive":
        return RemotiveAdapter(**common)
    if source.source_type == "wwr":
        return WeWorkRemotelyAdapter(**common)
    raise ValueError(f"Unsupported source type: {source.source_type}")
