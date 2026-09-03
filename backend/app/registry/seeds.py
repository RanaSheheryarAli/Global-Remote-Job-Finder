import json
from importlib.resources import files
from typing import Any


def load_phase3_sources() -> list[dict[str, Any]]:
    resource = files("app.registry").joinpath("phase3_sources.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("Phase 3 registry must contain a sources list")
    return sources
