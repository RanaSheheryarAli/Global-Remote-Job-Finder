from __future__ import annotations

import httpx

from app.ingestion.contracts import NormalizedJob, SourceJobSummary
from app.ingestion.http import PublicJsonAdapter
from app.ingestion.normalization import html_to_text, parse_datetime, require_https_url, stable_hash


class HimalayasAdapter(PublicJsonAdapter):
    endpoint = "https://himalayas.app/jobs/api"

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        max_pages: int = 10,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.max_pages = max_pages
        super().__init__(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            client=client,
        )

    async def list_jobs(self) -> list[SourceJobSummary]:
        summaries: list[SourceJobSummary] = []
        cursor: str | None = None
        for _ in range(self.max_pages):
            params = {"limit": "20"}
            if cursor:
                params["cursor"] = cursor
            payload = await self._get_json(self.endpoint, params=params)
            if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
                raise ValueError("Himalayas returned an invalid jobs response")
            for job in payload["jobs"]:
                if not isinstance(job, dict) or not job.get("guid"):
                    continue
                application_url = require_https_url(str(job.get("applicationLink") or ""))
                restrictions = job.get("locationRestrictions") or []
                location = "Worldwide" if not restrictions else ", ".join(map(str, restrictions))
                published_at = parse_datetime(job.get("pubDate"))
                summaries.append(
                    SourceJobSummary(
                        source_job_id=str(job["guid"]),
                        title=str(job.get("title") or "").strip(),
                        location_text=location,
                        application_url=application_url,
                        source_updated_at=published_at,
                        raw_payload=job,
                        force_normalize=True,
                    )
                )
            cursor = payload.get("nextCursor")
            if not cursor:
                break
        return summaries

    async def fetch_and_normalize(self, summary: SourceJobSummary) -> NormalizedJob:
        job = summary.raw_payload
        application_url = require_https_url(str(job.get("applicationLink") or ""))
        description_html = str(job.get("description") or "")
        published_at = parse_datetime(job.get("pubDate"))
        restrictions = [str(value).upper() for value in job.get("locationRestrictions") or []]
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
