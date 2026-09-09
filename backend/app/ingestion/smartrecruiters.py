from __future__ import annotations

import re

import httpx

from app.ingestion.contracts import NormalizedJob, SourceJobSummary
from app.ingestion.http import PublicJsonAdapter
from app.ingestion.normalization import html_to_text, parse_datetime, require_https_url, stable_hash

COMPANY_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class SmartRecruitersAdapter(PublicJsonAdapter):
    base_url = "https://api.smartrecruiters.com/v1/companies"

    def __init__(
        self,
        company_identifier: str,
        *,
        company_name: str | None = None,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not COMPANY_ID_RE.fullmatch(company_identifier):
            raise ValueError("Invalid SmartRecruiters company identifier")
        self.company_identifier = company_identifier
        self.company_name = company_name or company_identifier
        super().__init__(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            client=client,
        )

    async def list_jobs(self) -> list[SourceJobSummary]:
        summaries: list[SourceJobSummary] = []
        offset = 0
        while True:
            payload = await self._get_json(
                f"{self.base_url}/{self.company_identifier}/postings",
                params={
                    "limit": "100",
                    "offset": str(offset),
                    "destination": "PUBLIC",
                    "locationType": "REMOTE",
                },
            )
            if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
                raise ValueError("SmartRecruiters returned an invalid postings response")
            jobs = payload["content"]
            for job in jobs:
                if not isinstance(job, dict) or not job.get("id") or not job.get("ref"):
                    continue
                location = job.get("location") or {}
                summaries.append(
                    SourceJobSummary(
                        source_job_id=str(job["id"]),
                        title=str(job.get("name") or "").strip(),
                        location_text=location.get("fullLocation"),
                        application_url=str(job["ref"]),
                        source_updated_at=parse_datetime(job.get("releasedDate")),
                        raw_payload=job,
                    )
                )
            offset += len(jobs)
            total = int(payload.get("totalFound") or 0)
            if not jobs or offset >= total or offset >= 2000:
                break
        return summaries

    async def fetch_and_normalize(self, summary: SourceJobSummary) -> NormalizedJob:
        detail = await self._get_json(summary.application_url)
        if not isinstance(detail, dict):
            raise ValueError("SmartRecruiters returned an invalid posting detail")
        sections = (detail.get("jobAd") or {}).get("sections") or {}
        description_html = "\n".join(
            str(section.get("text") or "")
            for section in sections.values()
            if isinstance(section, dict)
        )
        posting_url = require_https_url(str(detail.get("postingUrl") or ""))
        apply_url = require_https_url(str(detail.get("applyUrl") or posting_url))
        location = detail.get("location") or {}
        published_at = parse_datetime(detail.get("releasedDate"))
        country = str(location.get("country") or "").upper()
        employment = detail.get("typeOfEmployment") or {}
        material = {
            "id": summary.source_job_id,
            "title": detail.get("name"),
            "description": description_html,
            "posting_url": posting_url,
            "apply_url": apply_url,
            "released": detail.get("releasedDate"),
            "location": location,
        }
        return NormalizedJob(
            source_job_id=summary.source_job_id,
            employer_name=str((detail.get("company") or {}).get("name") or self.company_name),
            title=str(detail.get("name") or summary.title).strip(),
            location_text=location.get("fullLocation") or summary.location_text,
            description_html=description_html,
            description_text=html_to_text(description_html),
            application_url=apply_url,
            first_published_at=published_at,
            source_updated_at=published_at,
            content_hash=stable_hash(material),
            raw_payload=detail,
            source_url=posting_url,
            # The list request itself is constrained to locationType=REMOTE.
            workplace_type="remote",
            employment_type=employment.get("label") or employment.get("id"),
            source_country_codes=[country] if len(country) == 2 else [],
        )
