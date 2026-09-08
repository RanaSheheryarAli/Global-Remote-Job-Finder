from __future__ import annotations

import httpx

from app.ingestion.contracts import NormalizedJob, SourceJobSummary
from app.ingestion.http import PublicJsonAdapter
from app.ingestion.normalization import html_to_text, parse_datetime, require_https_url, stable_hash

REMOTIVE_HOSTS = {"remotive.com", "www.remotive.com"}


class RemotiveAdapter(PublicJsonAdapter):
    endpoint = "https://remotive.com/api/remote-jobs"

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            client=client,
        )

    async def list_jobs(self) -> list[SourceJobSummary]:
        payload = await self._get_json(self.endpoint, params={"category": "software-dev"})
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("Remotive returned an invalid jobs response")
        summaries: list[SourceJobSummary] = []
        for job in payload["jobs"]:
            if not isinstance(job, dict) or job.get("id") is None:
                continue
            url = require_https_url(str(job.get("url") or ""), allowed_hosts=REMOTIVE_HOSTS)
            summaries.append(
                SourceJobSummary(
                    source_job_id=str(job["id"]),
                    title=str(job.get("title") or "").strip(),
                    location_text=job.get("candidate_required_location"),
                    application_url=url,
                    source_updated_at=parse_datetime(job.get("publication_date")),
                    raw_payload=job,
                    force_normalize=True,
                )
            )
        return summaries

    async def fetch_and_normalize(self, summary: SourceJobSummary) -> NormalizedJob:
        job = summary.raw_payload
        url = require_https_url(str(job.get("url") or ""), allowed_hosts=REMOTIVE_HOSTS)
        description_html = str(job.get("description") or "")
        published_at = parse_datetime(job.get("publication_date"))
        material = {
            "id": summary.source_job_id,
            "title": summary.title,
            "company": job.get("company_name"),
            "description": description_html,
            "url": url,
            "published_at": job.get("publication_date"),
            "location": job.get("candidate_required_location"),
        }
        return NormalizedJob(
            source_job_id=summary.source_job_id,
            employer_name=str(job.get("company_name") or "Unknown company"),
            title=summary.title,
            location_text=summary.location_text,
            description_html=description_html,
            description_text=html_to_text(description_html),
            application_url=url,
            first_published_at=published_at,
            source_updated_at=published_at,
            content_hash=stable_hash(material),
            raw_payload=job,
            source_url=url,
            workplace_type="remote",
            employment_type=job.get("job_type"),
            compensation={"display": job["salary"]} if job.get("salary") else None,
            attribution_name="Remotive",
            attribution_url=url,
        )
