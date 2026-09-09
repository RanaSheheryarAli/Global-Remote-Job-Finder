import json
from pathlib import Path

import httpx
import pytest

from app.ingestion.ashby import AshbyAdapter
from app.ingestion.himalayas import HimalayasAdapter
from app.ingestion.jobicy import JobicyAdapter
from app.ingestion.lever import LeverAdapter
from app.ingestion.remoteok import RemoteOkAdapter
from app.ingestion.remotive import RemotiveAdapter
from app.ingestion.smartrecruiters import SmartRecruitersAdapter
from app.ingestion.wwr import WeWorkRemotelyAdapter

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


@pytest.mark.asyncio
async def test_himalayas_adapter_reads_location_restrictions() -> None:
    payload = {
        "jobs": [
            {
                "guid": "him-1",
                "title": "Senior Software Engineer",
                "companyName": "Example",
                "applicationLink": "https://example.com/jobs/him-1",
                "description": "<p>Build React systems.</p>",
                "pubDate": "2026-09-08T08:00:00Z",
                "locationRestrictions": ["PK", "AE"],
            }
        ],
        "nextCursor": None,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/search")
        assert (
            request.url.params.get("worldwide") == "true"
            or request.url.params.get("country") == "PK"
        )
        page = int(request.url.params["page"])
        return httpx.Response(200, json=payload if page == 1 else {"jobs": [], "totalCount": 1})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = HimalayasAdapter(client=client)
        summaries = await adapter.list_jobs()
        job = await adapter.fetch_and_normalize(summaries[0])

    assert summaries[0].location_text == "PK, AE"
    assert job.source_country_codes == ["PK", "AE"]
    assert job.attribution_name == "Himalayas"


@pytest.mark.asyncio
async def test_jobicy_adapter_requests_engineering_jobs() -> None:
    payload = {
        "jobs": [
            {
                "id": 1,
                "jobTitle": "React Developer",
                "companyName": "Example",
                "url": "https://jobicy.com/jobs/1",
                "jobGeo": "Anywhere",
                "jobDescription": "<p>Build React applications.</p>",
                "pubDate": "2026-09-08T08:00:00Z",
                "jobType": ["full-time"],
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["industry"] == "engineering"
        assert request.url.params["count"] == "200"
        assert request.url.params["geo"] == "anywhere"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = JobicyAdapter(client=client)
        summaries = await adapter.list_jobs()
        job = await adapter.fetch_and_normalize(summaries[0])

    assert job.employment_type == "full-time"
    assert job.attribution_name == "Jobicy"


@pytest.mark.asyncio
async def test_remotive_adapter_uses_software_category_and_attribution() -> None:
    payload = {
        "jobs": [
            {
                "id": 2,
                "title": "Backend Software Engineer",
                "company_name": "Example",
                "url": "https://remotive.com/remote-jobs/software-dev/example-2",
                "candidate_required_location": "Worldwide",
                "description": "<p>Build Python APIs.</p>",
                "publication_date": "2026-09-08T08:00:00Z",
                "job_type": "full_time",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["category"] == "software-dev"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = RemotiveAdapter(client=client)
        summaries = await adapter.list_jobs()
        job = await adapter.fetch_and_normalize(summaries[0])

    assert job.location_text == "Worldwide"
    assert job.attribution_name == "Remotive"
    assert job.attribution_url == job.source_url


@pytest.mark.asyncio
async def test_wwr_adapter_parses_programming_rss() -> None:
    rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss><channel><item>
      <title>Example: Senior React Engineer</title>
      <link>https://weworkremotely.com/remote-jobs/example-react</link>
      <guid>wwr-1</guid>
      <pubDate>Tue, 08 Sep 2026 08:00:00 +0000</pubDate>
      <region>Anywhere</region>
      <description><![CDATA[<p>Build React applications.</p>]]></description>
    </item></channel></rss>"""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=rss))
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = WeWorkRemotelyAdapter(client=client)
        summaries = await adapter.list_jobs()
        job = await adapter.fetch_and_normalize(summaries[0])

    assert job.employer_name == "Example"
    assert job.title == "Senior React Engineer"
    assert job.location_text == "Anywhere"
    assert job.attribution_name == "We Work Remotely"


@pytest.mark.asyncio
async def test_smartrecruiters_adapter_reads_public_remote_jobs() -> None:
    summary_payload = {
        "totalFound": 1,
        "content": [
            {
                "id": "sr-1",
                "name": "Senior Backend Engineer",
                "ref": "https://api.smartrecruiters.com/v1/companies/Example/postings/sr-1",
                "releasedDate": "2026-09-09T08:00:00Z",
                "location": {"fullLocation": "Worldwide", "remote": True},
            }
        ],
    }
    detail_payload = {
        **summary_payload["content"][0],
        "company": {"name": "Example"},
        "postingUrl": "https://jobs.smartrecruiters.com/Example/sr-1",
        "applyUrl": "https://jobs.smartrecruiters.com/Example/sr-1?oga=true",
        "jobAd": {
            "sections": {
                "jobDescription": {"text": "<p>Build Python APIs.</p>"},
                "qualifications": {"text": "<p>Python and PostgreSQL required.</p>"},
            }
        },
        "typeOfEmployment": {"label": "Full-time"},
        "location": {"fullLocation": "Worldwide", "remote": True},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/postings"):
            assert request.url.params["locationType"] == "REMOTE"
            return httpx.Response(200, json=summary_payload)
        return httpx.Response(200, json=detail_payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SmartRecruitersAdapter("Example", company_name="Example", client=client)
        summaries = await adapter.list_jobs()
        job = await adapter.fetch_and_normalize(summaries[0])

    assert job.employer_name == "Example"
    assert job.workplace_type == "remote"
    assert job.first_published_at.isoformat() == "2026-09-09T08:00:00+00:00"
    assert job.application_url.endswith("?oga=true")
