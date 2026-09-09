from __future__ import annotations

import httpx

from app.ingestion.contracts import NormalizedJob, SourceJobSummary
from app.ingestion.http import PublicJsonAdapter
from app.ingestion.normalization import html_to_text, parse_datetime, require_https_url, stable_hash


class HimalayasAdapter(PublicJsonAdapter):
    endpoint = "https://himalayas.app/jobs/api"
    search_endpoint = "https://himalayas.app/jobs/api/search"

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        max_pages: int = 5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.max_pages = max_pages
        super().__init__(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            client=client,
        )

    async def list_jobs(self) -> list[SourceJobSummary]:
        summaries: dict[str, SourceJobSummary] = {}
        searches = (
            {"worldwide": "true", "sort": "recent"},
            {"country": "PK", "exclude_worldwide": "true", "sort": "recent"},
        )
        for filters in searches:
            search_received = 0
            for page in range(1, self.max_pages + 1):
                payload = await self._get_json(
                    self.search_endpoint,
                    params={**filters, "page": str(page)},
                )
                if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
                    raise ValueError("Himalayas returned an invalid jobs response")
                jobs = payload["jobs"]
                search_received += len(jobs)
                for job in jobs:
                    if not isinstance(job, dict) or not job.get("guid"):
                        continue
                    application_url = require_https_url(str(job.get("applicationLink") or ""))
                    restrictions = job.get("locationRestrictions") or []
                    labels = [
                        str(value.get("name") or value.get("alpha2") or "")
                        if isinstance(value, dict)
                        else str(value)
                        for value in restrictions
                    ]
                    location = "Worldwide" if not labels else ", ".join(filter(None, labels))
                    published_at = parse_datetime(job.get("pubDate"))
                    source_job_id = str(job["guid"])
                    summaries[source_job_id] = SourceJobSummary(
                        source_job_id=source_job_id,
                        title=str(job.get("title") or "").strip(),
                        location_text=location,
                        application_url=application_url,
                        source_updated_at=published_at,
                        raw_payload=job,
                        force_normalize=True,
                    )
                total = payload.get("totalCount")
                if not jobs or (total is not None and search_received >= int(total)):
                    break
        return list(summaries.values())

    async def fetch_and_normalize(self, summary: SourceJobSummary) -> NormalizedJob:
        job = summary.raw_payload
        application_url = require_https_url(str(job.get("applicationLink") or ""))
        description_html = str(job.get("description") or "")
        published_at = parse_datetime(job.get("pubDate"))
        restrictions = [
            str(value.get("alpha2") or value.get("name") or "").upper()
            if isinstance(value, dict)
            else str(value).upper()
            for value in job.get("locationRestrictions") or []
        ]
        country_codes = [value for value in restrictions if len(value) == 2]
        compensation = {
            key: value
            for key, value in {
                "min": job.get("minSalary"),
                "max": job.get("maxSalary"),
                "currency": job.get("currency"),
                "interval": job.get("salaryPeriod"),
            }.items()
            if value is not None
        }
        material = {
            "id": summary.source_job_id,
            "title": summary.title,
            "company": job.get("companyName"),
            "description": description_html,
            "application_url": application_url,
            "published_at": job.get("pubDate"),
            "restrictions": restrictions,
        }
        return NormalizedJob(
            source_job_id=summary.source_job_id,
            employer_name=str(job.get("companyName") or "Unknown company"),
            title=summary.title,
            location_text=summary.location_text,
            description_html=description_html,
            description_text=html_to_text(description_html),
            application_url=application_url,
            first_published_at=published_at,
            source_updated_at=published_at,
            content_hash=stable_hash(material),
            raw_payload=job,
            source_url=application_url,
            workplace_type="remote",
            employment_type=job.get("employmentType"),
            compensation=compensation or None,
            attribution_name="Himalayas",
            attribution_url=application_url,
            source_country_codes=country_codes,
        )
