import json
from pathlib import Path

import httpx
import pytest

from app.ingestion.ashby import AshbyAdapter
from app.ingestion.lever import LeverAdapter
from app.ingestion.remoteok import RemoteOkAdapter

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_lever_adapter_preserves_hosted_and_apply_urls() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["mode"] == "json"
        return httpx.Response(200, json=load_fixture("lever_jobs.json"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = LeverAdapter("example", company_name="Example", client=client)
        summaries = await adapter.list_jobs()
        job = await adapter.fetch_and_normalize(summaries[0])

    assert job.first_published_at is None
    assert job.source_url == "https://jobs.lever.co/example/lever-101"
    assert job.application_url.endswith("/apply")
    assert job.workplace_type == "remote"
    assert job.compensation == {
        "currency": "USD",
        "interval": "year",
        "min": 100000,
        "max": 140000,
    }


@pytest.mark.asyncio
async def test_ashby_adapter_filters_unlisted_and_captures_compensation() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=load_fixture("ashby_jobs.json"))
    )
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = AshbyAdapter("Example", company_name="Example", client=client)
        summaries = await adapter.list_jobs()
        job = await adapter.fetch_and_normalize(summaries[0])

    assert len(summaries) == 1
    assert job.first_published_at.isoformat() == "2026-09-03T07:10:00+00:00"
    assert job.workplace_type == "Remote"
    assert job.compensation == {"compensationTierSummary": "$120K - $150K"}


@pytest.mark.asyncio
async def test_remote_ok_adapter_enforces_attribution_and_link_back() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=load_fixture("remoteok_jobs.json"))
    )
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RemoteOkAdapter(client=client)
        summaries = await adapter.list_jobs()
        job = await adapter.fetch_and_normalize(summaries[0])

    assert job.employer_name == "Example Remote Company"
    assert job.attribution_name == "Remote OK"
    assert job.attribution_url == job.source_url
    assert job.description_text == "Build remote systems."


@pytest.mark.asyncio
async def test_remote_ok_adapter_rejects_missing_legal_metadata() -> None:
    payload = [{"last_updated": 1}, *load_fixture("remoteok_jobs.json")[1:]]
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RemoteOkAdapter(client=client)
        with pytest.raises(ValueError, match="attribution terms"):
            await adapter.list_jobs()
