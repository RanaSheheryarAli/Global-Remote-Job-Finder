from __future__ import annotations

import re
from typing import Any

import httpx

from app.ingestion.contracts import NormalizedJob, SourceJobSummary
from app.ingestion.http import PublicJsonAdapter
from app.ingestion.normalization import html_to_text, require_https_url, stable_hash

SITE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
LEVER_HOSTS = {"jobs.lever.co", "jobs.eu.lever.co"}


class LeverAdapter(PublicJsonAdapter):
    def __init__(
        self,
        site: str,
        *,
        company_name: str,
        region: str = "global",
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not SITE_RE.fullmatch(site):
            raise ValueError("Invalid Lever site identifier")
        if region not in {"global", "eu"}:
            raise ValueError("Lever region must be 'global' or 'eu'")
        self.site = site
        self.company_name = company_name
        api_host = "api.eu.lever.co" if region == "eu" else "api.lever.co"
        self.base_url = f"https://{api_host}/v0/postings/{site}"
        super().__init__(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            client=client,
        )

    async def list_jobs(self) -> list[SourceJobSummary]:
        jobs: list[dict[str, Any]] = []
        skip = 0
        page_size = 100
        for _ in range(100):
            payload = await self._get_json(
                self.base_url,
                params={"mode": "json", "skip": skip, "limit": page_size},
            )
            if not isinstance(payload, list):
                raise ValueError("Lever returned a non-list JSON response")
            page = [item for item in payload if isinstance(item, dict)]
            jobs.extend(page)
            if len(page) < page_size:
                break
            skip += page_size
        else:
            raise ValueError("Lever pagination exceeded the safety limit")

        summaries: list[SourceJobSummary] = []
        for job in jobs:
            hosted_url = require_https_url(str(job["hostedUrl"]), allowed_hosts=LEVER_HOSTS)
            apply_url = require_https_url(
                str(job.get("applyUrl") or hosted_url),
                allowed_hosts=LEVER_HOSTS,
            )
            summaries.append(
                SourceJobSummary(
                    source_job_id=str(job["id"]),
                    title=str(job["text"]).strip(),
                    location_text=(job.get("categories") or {}).get("location"),
                    application_url=apply_url,
                    source_updated_at=None,
                    raw_payload=job,
                )
            )
        return summaries

    async def fetch_and_normalize(self, summary: SourceJobSummary) -> NormalizedJob:
        job = summary.raw_payload
        lists_html = "".join(
            f"<h3>{item.get('text', '')}</h3>{item.get('content', '')}"
            for item in job.get("lists", [])
            if isinstance(item, dict)
        )
        description_html = "".join(
            [
                str(job.get("description") or ""),
                lists_html,
                str(job.get("additional") or ""),
            ]
        )
        hosted_url = require_https_url(str(job["hostedUrl"]), allowed_hosts=LEVER_HOSTS)
        apply_url = require_https_url(
            str(job.get("applyUrl") or hosted_url),
            allowed_hosts=LEVER_HOSTS,
        )
        compensation = job.get("salaryRange")
        country = str(job.get("country") or "").strip().upper()
        country_codes = [country] if re.fullmatch(r"[A-Z]{2}", country) else []
        material_payload = {
            "source_job_id": summary.source_job_id,
            "title": summary.title,
            "location_text": summary.location_text,
            "description_html": description_html,
            "source_url": hosted_url,
            "application_url": apply_url,
            "workplace_type": job.get("workplaceType"),
            "employment_type": (job.get("categories") or {}).get("commitment"),
            "compensation": compensation,
            "country_codes": country_codes,
        }
        return NormalizedJob(
            source_job_id=summary.source_job_id,
            employer_name=self.company_name,
            title=summary.title,
            location_text=summary.location_text,
            description_html=description_html,
            description_text=html_to_text(description_html),
            application_url=apply_url,
            first_published_at=None,
            source_updated_at=None,
            content_hash=stable_hash(material_payload),
            raw_payload=job,
            source_url=hosted_url,
            workplace_type=job.get("workplaceType"),
            employment_type=(job.get("categories") or {}).get("commitment"),
            compensation=compensation if isinstance(compensation, dict) else None,
            source_country_codes=country_codes,
        )
