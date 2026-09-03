from __future__ import annotations

import re

import httpx

from app.ingestion.contracts import NormalizedJob, SourceJobSummary
from app.ingestion.http import PublicJsonAdapter
from app.ingestion.normalization import parse_datetime, require_https_url, stable_hash

BOARD_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ASHBY_HOSTS = {"jobs.ashbyhq.com"}


class AshbyAdapter(PublicJsonAdapter):
    base_url = "https://api.ashbyhq.com/posting-api/job-board"

    def __init__(
        self,
        board_name: str,
        *,
        company_name: str,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not BOARD_RE.fullmatch(board_name):
            raise ValueError("Invalid Ashby board name")
        self.board_name = board_name
        self.company_name = company_name
        super().__init__(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            client=client,
        )

    async def list_jobs(self) -> list[SourceJobSummary]:
        payload = await self._get_json(
            f"{self.base_url}/{self.board_name}",
            params={"includeCompensation": "true"},
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("Ashby returned an invalid jobs response")

        summaries: list[SourceJobSummary] = []
        for job in payload["jobs"]:
            if not isinstance(job, dict) or job.get("isListed") is False:
                continue
            apply_url = require_https_url(
                str(job.get("applyUrl") or job["jobUrl"]),
                allowed_hosts=ASHBY_HOSTS,
            )
            summaries.append(
                SourceJobSummary(
                    source_job_id=str(job["id"]),
                    title=str(job["title"]).strip(),
                    location_text=job.get("location"),
                    application_url=apply_url,
                    source_updated_at=parse_datetime(job.get("publishedAt")),
                    raw_payload=job,
                    force_normalize=True,
                )
            )
        return summaries

    async def fetch_and_normalize(self, summary: SourceJobSummary) -> NormalizedJob:
        job = summary.raw_payload
        source_url = require_https_url(str(job["jobUrl"]), allowed_hosts=ASHBY_HOSTS)
        apply_url = require_https_url(
            str(job.get("applyUrl") or source_url),
            allowed_hosts=ASHBY_HOSTS,
        )
        description_html = str(job.get("descriptionHtml") or "")
        published_at = parse_datetime(job.get("publishedAt"))
        compensation = job.get("compensation")
        material_payload = {
            "source_job_id": summary.source_job_id,
            "title": summary.title,
            "location_text": summary.location_text,
            "description_html": description_html,
            "source_url": source_url,
            "application_url": apply_url,
            "published_at": job.get("publishedAt"),
            "workplace_type": job.get("workplaceType"),
            "employment_type": job.get("employmentType"),
            "compensation": compensation,
        }
        return NormalizedJob(
            source_job_id=summary.source_job_id,
            employer_name=self.company_name,
            title=summary.title,
            location_text=summary.location_text,
            description_html=description_html,
            description_text=str(job.get("descriptionPlain") or ""),
            application_url=apply_url,
            first_published_at=published_at,
            source_updated_at=published_at,
            content_hash=stable_hash(material_payload),
            raw_payload=job,
            source_url=source_url,
            workplace_type=job.get("workplaceType"),
            employment_type=job.get("employmentType"),
            compensation=compensation if isinstance(compensation, dict) else None,
        )
