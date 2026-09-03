from __future__ import annotations

import httpx

from app.ingestion.contracts import NormalizedJob, SourceJobSummary
from app.ingestion.http import PublicJsonAdapter
from app.ingestion.normalization import (
    html_to_text,
    parse_datetime,
    require_https_url,
    stable_hash,
)

REMOTE_OK_HOSTS = {"remoteok.com", "www.remoteok.com"}


class RemoteOkAdapter(PublicJsonAdapter):
    endpoint = "https://remoteok.com/api"

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            client=client,
        )

    async def list_jobs(self) -> list[SourceJobSummary]:
        payload = await self._get_json(self.endpoint)
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            raise ValueError("Remote OK returned an invalid feed")
        legal = str(payload[0].get("legal") or "")
        if "link back" not in legal.lower() or "remote ok" not in legal.lower():
            raise ValueError("Remote OK attribution terms are missing or changed")

        summaries: list[SourceJobSummary] = []
        for job in payload[1:]:
            if not isinstance(job, dict) or not job.get("id"):
                continue
            source_url = require_https_url(
                str(job.get("url") or job.get("apply_url") or ""),
                allowed_hosts=REMOTE_OK_HOSTS,
            )
            summaries.append(
                SourceJobSummary(
                    source_job_id=str(job["id"]),
                    title=str(job.get("position") or "Untitled role").strip(),
                    location_text=job.get("location") or None,
                    application_url=source_url,
                    source_updated_at=parse_datetime(job.get("date")),
                    raw_payload={"legal": legal, "job": job},
                    force_normalize=True,
                )
            )
        return summaries

    async def fetch_and_normalize(self, summary: SourceJobSummary) -> NormalizedJob:
        job = summary.raw_payload["job"]
        source_url = require_https_url(
            str(job.get("url") or job.get("apply_url") or ""),
            allowed_hosts=REMOTE_OK_HOSTS,
        )
        description_html = str(job.get("description") or "")
        published_at = parse_datetime(job.get("date"))
        salary_min = job.get("salary_min") or None
        salary_max = job.get("salary_max") or None
        compensation = None
        if salary_min is not None or salary_max is not None:
            compensation = {"min": salary_min, "max": salary_max, "currency": None}
        material_payload = {
            "source_job_id": summary.source_job_id,
            "employer_name": job.get("company"),
            "title": summary.title,
            "location_text": summary.location_text,
            "description_html": description_html,
            "source_url": source_url,
            "published_at": job.get("date"),
            "compensation": compensation,
        }
        return NormalizedJob(
            source_job_id=summary.source_job_id,
            employer_name=str(job.get("company") or "Unknown employer"),
            title=summary.title,
            location_text=summary.location_text,
            description_html=description_html,
            description_text=html_to_text(description_html),
            application_url=source_url,
            first_published_at=published_at,
            source_updated_at=published_at,
            content_hash=stable_hash(material_payload),
            raw_payload=summary.raw_payload,
            source_url=source_url,
            workplace_type="remote",
            compensation=compensation,
            attribution_name="Remote OK",
            attribution_url=source_url,
        )
