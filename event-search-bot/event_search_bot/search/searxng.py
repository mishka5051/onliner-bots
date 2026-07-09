import logging
from urllib.parse import urlparse

import httpx

from event_search_bot.search.models import SearchResult

logger = logging.getLogger(__name__)


class SearXngSearchProvider:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 60.0,
        pages_max: int = 2,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._pages_max = max(1, pages_max)

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        return await self._search_pages(query, limit=limit)

    async def _search_pages(self, query: str, *, limit: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        seen_urls: set[str] = set()
        page_no = 1

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                for page_no in range(1, self._pages_max + 1):
                    if len(results) >= limit:
                        break

                    params: dict[str, str | int] = {
                        "q": query,
                        "format": "json",
                        "language": "ru-RU",
                        "pageno": page_no,
                    }

                    response = await client.get(f"{self._base_url}/search", params=params)
                    response.raise_for_status()
                    payload = response.json()

                    raw_results = payload.get("results", [])
                    if not raw_results:
                        break

                    added = 0
                    for item in raw_results:
                        if len(results) >= limit:
                            break

                        link = item.get("url")
                        title = item.get("title")
                        if not link or not title:
                            continue

                        normalized = link.rstrip("/")
                        if normalized in seen_urls:
                            continue
                        seen_urls.add(normalized)

                        parsed = urlparse(link)
                        source_domain = parsed.netloc.lower().removeprefix("www.")

                        results.append(
                            SearchResult(
                                title=title.strip(),
                                snippet=(item.get("content") or "").strip() or None,
                                link=link,
                                source_domain=source_domain,
                            )
                        )
                        added += 1

                    if added == 0:
                        break
        except httpx.HTTPStatusError:
            logger.exception("SearXNG HTTP error on page %s", page_no)
            if not results:
                raise
        except httpx.RequestError:
            logger.exception("SearXNG request failed")
            if not results:
                raise

        if not results:
            logger.warning("SearXNG returned no results for query=%r", query)

        return results
