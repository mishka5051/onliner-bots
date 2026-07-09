from __future__ import annotations

import logging

import httpx

from event_search_bot.config import Settings, get_settings
from event_search_bot.search.filter import rank_results
from event_search_bot.search.models import SearchResult
from event_search_bot.search.searxng import SearXngSearchProvider

logger = logging.getLogger(__name__)


class EventSearchService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._provider = SearXngSearchProvider(
            base_url=self._settings.searxng_base_url,
            timeout=self._settings.search_timeout,
            pages_max=self._settings.search_pages_max,
        )

    def build_query(self, user_text: str) -> str:
        query = user_text.strip()
        suffix = (self._settings.query_suffix or "").strip()
        if suffix and suffix.lower() not in query.lower():
            query = f"{query} {suffix}"
        return query

    async def search_events(self, user_text: str) -> tuple[str, list[SearchResult]]:
        query = self.build_query(user_text)
        fetch_limit = max(self._settings.search_results_limit * 3, 20)

        try:
            raw = await self._provider.search(query, limit=fetch_limit)
        except httpx.HTTPError as exc:
            logger.exception("Search failed for query=%r", query)
            raise RuntimeError(
                "Поиск недоступен. Проверьте, что SearXNG запущен "
                f"({self._settings.searxng_base_url})."
            ) from exc

        ranked = rank_results(raw, limit=self._settings.search_results_limit)
        return query, ranked
