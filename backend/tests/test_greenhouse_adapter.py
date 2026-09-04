import json
from pathlib import Path

import httpx
import pytest

from app.ingestion.greenhouse import GreenhouseAdapter

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_greenhouse_adapter_lists_and_normalizes_job() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path.endswith("/jobs"):
            assert request.url.params["content"] == "true"
            return httpx.Response(200, json=load_fixture("greenhouse_jobs.json"))
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GreenhouseAdapter("example", client=client)
        summaries = await adapter.list_jobs()
        job = await adapter.fetch_and_normalize(summaries[0])

    assert len(summaries) == 1
    assert summaries[0].source_job_id == "101"
    assert job.first_published_at.isoformat() == "2026-09-03T08:00:00+00:00"
    assert job.description_text == "Build reliable products with Python and TypeScript."
    assert len(job.content_hash) == 64
    assert requested_paths == ["/v1/boards/example/jobs"]


def test_greenhouse_adapter_rejects_unsafe_board_token() -> None:
    with pytest.raises(ValueError):
        GreenhouseAdapter("../../secret")
