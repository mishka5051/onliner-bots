"""Сбор событий из доверенных каталогов с проверкой по запросу."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from event_search_bot.pipeline.catalog_links import CatalogLinkExtractor
from event_search_bot.pipeline.page_fetcher import FetchSkipped, HttpPageFetcher
from event_search_bot.pipeline.trusted_catalogs import (
    TrustedCatalog,
    all_trusted_catalogs,
    event_matches_query,
)
from event_search_bot.search.models import SearchResult

logger = logging.getLogger(__name__)


async def collect_trusted_catalog_hits(
    user_query: str,
    *,
    fetcher: HttpPageFetcher | None = None,
    max_per_catalog: int = 30,
) -> list[SearchResult]:
    own_fetcher = fetcher is None
    fetcher = fetcher or HttpPageFetcher(timeout=20.0)
    extractor = CatalogLinkExtractor(max_links=max_per_catalog)
    results: list[SearchResult] = []
    seen: set[str] = set()

    try:
        for catalog in all_trusted_catalogs():
            try:
                page = await fetcher.fetch(catalog.url, title=catalog.name, snippet=None)
            except FetchSkipped:
                logger.info("Skipped trusted catalog fetch: %s", catalog.url)
                continue
            except Exception:
                logger.exception("Trusted catalog fetch failed: %s", catalog.url)
                continue

            links = extractor.extract(page.html, catalog.url)
            for link in links:
                if not event_matches_query(
                    user_query=user_query,
                    title=link.title,
                    url=link.url,
                    tier=catalog.tier,
                ):
                    continue
                key = link.url.rstrip("/")
                if key in seen:
                    continue
                seen.add(key)
                domain = urlparse(link.url).netloc.lower().removeprefix("www.")
                results.append(
                    SearchResult(
                        title=link.title.strip(),
                        snippet=f"Каталог {catalog.name} (tier {catalog.tier})",
                        link=link.url,
                        source_domain=domain,
                    )
                )
    finally:
        if own_fetcher:
            await fetcher.aclose()

    logger.info(
        "Trusted catalogs for query=%r: %s event links",
        user_query,
        len(results),
    )
    return results
