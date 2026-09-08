from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx

from app.ingestion.contracts import NormalizedJob, SourceJobSummary
from app.ingestion.http import PublicJsonAdapter
from app.ingestion.normalization import html_to_text, require_https_url, stable_hash


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _value(item: ElementTree.Element, *names: str) -> str | None:
    wanted = {name.casefold() for name in names}
    for child in item:
        if _local_name(child.tag) in wanted and child.text:
            return child.text.strip()
    return None


class WeWorkRemotelyAdapter(PublicJsonAdapter):
    endpoint = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    allowed_hosts = {"weworkremotely.com", "www.weworkremotely.com"}

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

    @staticmethod
    def _published(value: str | None) -> datetime | None:
        return parsedate_to_datetime(value) if value else None

    async def list_jobs(self) -> list[SourceJobSummary]:
        xml = await self._get_text(self.endpoint)
        root = ElementTree.fromstring(xml)
        summaries: list[SourceJobSummary] = []
        items = (node for node in root.iter() if _local_name(node.tag) in {"item", "entry"})
        for item in items:
            url = require_https_url(
                _value(item, "link") or "",
                allowed_hosts=self.allowed_hosts,
            )
            title = _value(item, "title") or ""
            guid = _value(item, "guid", "id") or url
            published = self._published(_value(item, "pubdate", "published", "updated"))
            summaries.append(
                SourceJobSummary(
                    source_job_id=guid[-200:],
                    title=title.strip(),
                    location_text=_value(item, "region", "location"),
                    application_url=url,
                    source_updated_at=published,
                    raw_payload={"xml": ElementTree.tostring(item, encoding="unicode")},
                    force_normalize=True,
                )
            )
        if not summaries:
            raise ValueError("We Work Remotely returned an empty or invalid RSS feed")
        return summaries

    async def fetch_and_normalize(self, summary: SourceJobSummary) -> NormalizedJob:
        item = ElementTree.fromstring(summary.raw_payload["xml"])
        url = require_https_url(
            _value(item, "link") or "",
            allowed_hosts=self.allowed_hosts,
        )
        description_html = _value(item, "description", "summary", "content") or ""
        published = self._published(_value(item, "pubdate", "published", "updated"))
        employer = _value(item, "company", "author")
        title = summary.title
        if not employer and ":" in title:
            employer, title = (part.strip() for part in title.split(":", 1))
        material = {
            "id": summary.source_job_id,
            "title": title,
            "company": employer,
            "description": description_html,
            "url": url,
            "published_at": published.isoformat() if published else None,
        }
        return NormalizedJob(
            source_job_id=summary.source_job_id,
            employer_name=employer or "Unknown company",
            title=title,
            location_text=summary.location_text,
            description_html=description_html,
            description_text=html_to_text(description_html),
            application_url=url,
            first_published_at=published,
            source_updated_at=published,
            content_hash=stable_hash(material),
            raw_payload=summary.raw_payload,
            source_url=url,
            workplace_type="remote",
            attribution_name="We Work Remotely",
            attribution_url=url,
        )
