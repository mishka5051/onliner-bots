import logging
from urllib.parse import urlparse

import httpx

from app.application.ports.search_provider import SearchResult
from app.core.exceptions import SearchApiUnavailableError, SearchProviderError

logger = logging.getLogger(__name__)


class SearXngSearchProvider:
    def __init__(self, base_url: str, *, timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        params = {
            "q": query,
            "format": "json",
            "language": "ru-RU",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/search", params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception("SearXNG HTTP error")
            raise SearchProviderError(
                message="SearXNG returned an error",
                details={"status_code": exc.response.status_code},
            ) from exc
        except httpx.RequestError as exc:
            logger.exception("SearXNG request failed")
            raise SearchApiUnavailableError(
                message="SearXNG is unavailable",
                details={"reason": str(exc), "base_url": self._base_url},
            ) from exc

        raw_results = payload.get("results", [])
        results: list[SearchResult] = []

        for item in raw_results[:limit]:
            link = item.get("url")
            title = item.get("title")
            if not link or not title:
                continue

            parsed = urlparse(link)
            source_domain = parsed.netloc.lower().removeprefix("www.")

            results.append(
                SearchResult(
                    title=title,
                    snippet=item.get("content"),
                    link=link,
                    source_domain=source_domain,
                )
            )

        return results
