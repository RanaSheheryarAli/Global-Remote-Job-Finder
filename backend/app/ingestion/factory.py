from app.core.config import Settings
from app.ingestion.ashby import AshbyAdapter
from app.ingestion.contracts import SourceAdapter
from app.ingestion.greenhouse import GreenhouseAdapter
from app.ingestion.lever import LeverAdapter
from app.ingestion.remoteok import RemoteOkAdapter
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
    if source.source_type == "remoteok":
        return RemoteOkAdapter(**common)
    raise ValueError(f"Unsupported source type: {source.source_type}")
