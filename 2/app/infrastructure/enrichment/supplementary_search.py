import logging

from app.application.ports.search_provider import SearchProvider

logger = logging.getLogger(__name__)


class SupplementarySearchService:
    def __init__(self, search_provider: SearchProvider, *, limit: int = 3) -> None:
        self._search_provider = search_provider
        self._limit = limit

    async def collect_context(self, title: str) -> tuple[str, int]:
        queries = [
            f'"{title}" Минск дата',
            f'"{title}" бесплатно вход',
            f'"{title}" партнёры спонсоры',
            f'"{title}" посещаемость участников',
        ]
        snippets: list[str] = []
        mentions = 0
        for query in queries:
            try:
                results = await self._search_provider.search(query, limit=self._limit)
            except Exception:
                logger.debug("Supplementary search failed for %s", query, exc_info=True)
                continue
            mentions += len(results)
            for result in results:
                if result.snippet:
                    snippets.append(result.snippet)
        return "\n".join(snippets), mentions
