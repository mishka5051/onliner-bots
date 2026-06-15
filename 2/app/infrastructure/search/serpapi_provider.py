import logging
from urllib.parse import urlparse

import httpx

from app.application.ports.search_provider import SearchResult
from app.core.exceptions import SearchApiUnavailableError, SearchProviderError

logger = logging.getLogger(__name__)

SERPAPI_BASE_URL = "https://serpapi.com/search.json"


class SerpApiSearchProvider:
    def __init__(self, api_key: str, *, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        params = {
            "engine": "google",
            "q": query,
            "api_key": self._api_key,
            "num": limit,
            "hl": "ru",
            "gl": "by",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(SERPAPI_BASE_URL, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception("SerpAPI HTTP error")
            raise SearchProviderError(
                message="Search API returned an error",
                details={"status_code": exc.response.status_code},
            ) from exc
        except httpx.RequestError as exc:
            logger.exception("SerpAPI request failed")
            raise SearchApiUnavailableError(
                message="Search API is unavailable",
                details={"reason": str(exc)},
            ) from exc

        if "error" in payload:
            raise SearchProviderError(
                message=payload.get("error", "Search API error"),
                details={"provider": "serpapi"},
            )

        organic_results = payload.get("organic_results", [])
        results: list[SearchResult] = []

        for item in organic_results[:limit]:
            link = item.get("link")
            title = item.get("title")
            if not link or not title:
                continue

            display_link = item.get("displayed_link") or item.get("source") or ""
            if display_link:
                source_domain = display_link.split(" ")[0].lower().removeprefix("www.")
            else:
                source_domain = urlparse(link).netloc.lower().removeprefix("www.")

            results.append(
                SearchResult(
                    title=title,
                    snippet=item.get("snippet"),
                    link=link,
                    source_domain=source_domain,
                )
            )

        return results
