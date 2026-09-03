from __future__ import annotations

import asyncio
from typing import Any

import httpx

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class PublicJsonAdapter:
    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_retries: int,
        client: httpx.AsyncClient | None,
    ) -> None:
        self.max_retries = max(1, max_retries)
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "GlobalRemoteJobTool/0.2 (+private job discovery)"},
        )

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _get_json(self, url: str, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self.client.get(url, **kwargs)
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                retryable = (
                    not isinstance(exc, httpx.HTTPStatusError)
                    or exc.response.status_code in RETRYABLE_STATUS_CODES
                )
                if not retryable or attempt == self.max_retries:
                    raise
                await asyncio.sleep(min(2 ** (attempt - 1), 4))
        raise RuntimeError("Public JSON request failed") from last_error
