from __future__ import annotations

import re

import httpx

from app.ingestion.contracts import NormalizedJob, SourceJobSummary
from app.ingestion.http import PublicJsonAdapter
from app.ingestion.normalization import (
    html_to_text,
    parse_datetime,
    require_https_url,
    stable_hash,
)

BOARD_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class GreenhouseAdapter(PublicJsonAdapter):
    base_url = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(
        self,
        board_token: str,
        *,
        company_name: str | None = None,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not BOARD_TOKEN_RE.fullmatch(board_token):
            raise ValueError("Invalid Greenhouse board token")
        self.board_token = board_token
        self.company_name = company_name or board_token
        super().__init__(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            client=client,
        )

    async def list_jobs(self) -> list[SourceJobSummary]:
        payload = await self._get_json(
            f"{self.base_url}/{self.board_token}/jobs", params={"content": "true"}
        )
        if not isinstance(payload, dict):
            raise ValueError("Greenhouse returned a non-object JSON response")
        jobs = payload.get("jobs", [])
        if not isinstance(jobs, list):
            raise ValueError("Greenhouse jobs field is not a list")

        summaries: list[SourceJobSummary] = []
        for job in jobs:
            source_job_id = str(job["id"])
            summaries.append(
                SourceJobSummary(
                    source_job_id=source_job_id,
                    title=str(job["title"]).strip(),
                    location_text=(job.get("location") or {}).get("name"),
                    application_url=str(job["absolute_url"]),
                    source_updated_at=parse_datetime(job.get("updated_at")),
                    raw_payload=job,
                )
            )
        return summaries

    async def fetch_and_normalize(self, summary: SourceJobSummary) -> NormalizedJob:
        detail = await self._get_json(
            f"{self.base_url}/{self.board_token}/jobs/{summary.source_job_id}"
        )
        if not isinstance(detail, dict):
            raise ValueError("Greenhouse returned a non-object job detail")
        description_html = str(detail.get("content") or summary.raw_payload.get("content") or "")
        source_url = require_https_url(str(detail.get("absolute_url") or summary.application_url))
        material_payload = {
            "source_job_id": summary.source_job_id,
            "title": str(detail.get("title") or summary.title).strip(),
            "location_text": (detail.get("location") or {}).get("name") or summary.location_text,
            "description_html": description_html,
            "application_url": source_url,
            "source_url": source_url,
            "first_published_at": detail.get("first_published"),
            "source_updated_at": detail.get("updated_at")
            or (summary.source_updated_at.isoformat() if summary.source_updated_at else None),
        }
        raw_payload = {"summary": summary.raw_payload, "detail": detail}
        return NormalizedJob(
            source_job_id=summary.source_job_id,
            employer_name=self.company_name,
            title=material_payload["title"],
            location_text=material_payload["location_text"],
            description_html=description_html,
            description_text=html_to_text(description_html),
            application_url=material_payload["application_url"],
            first_published_at=parse_datetime(detail.get("first_published")),
            source_updated_at=parse_datetime(detail.get("updated_at")) or summary.source_updated_at,
            content_hash=stable_hash(material_payload),
            raw_payload=raw_payload,
            source_url=source_url,
        )
