from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from event_search_bot.pipeline.enrich import EnrichmentContext, EnrichmentEngine
from event_search_bot.pipeline.models import EventRecord, PipelineProgress
from event_search_bot.pipeline.non_event import looks_like_real_event
from event_search_bot.pipeline.scoring_config import get_scoring_rules
from event_search_bot.search.filter import rank_results
from event_search_bot.search.models import SearchResult
from event_search_bot.search.searxng import SearXngSearchProvider

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[PipelineProgress], Awaitable[None] | None]


@dataclass
class DeepSearchResult:
    query: str
    built_query: str
    events: list[EventRecord] = field(default_factory=list)
    progress: PipelineProgress = field(default_factory=PipelineProgress)
    finished_at: datetime | None = None

    def suitable_events(self, *, min_score: int | None = None) -> list[EventRecord]:
        rules = get_scoring_rules()
        threshold = min_score if min_score is not None else rules.supplementary_borderline_min
        items = [
            event
            for event in self.events
            if event.relevance_status == "scored"
            and event.relevance_score is not None
            and event.relevance_score >= threshold
        ]
        return sorted(items, key=lambda item: item.relevance_score or 0, reverse=True)

    def top_shortlist(self, limit: int = 10) -> list[EventRecord]:
        rules = get_scoring_rules()
        items = [
            event
            for event in self.suitable_events(min_score=rules.shortlist_min_score)
            if event.is_minsk
            and looks_like_real_event(event_type=event.event_type, event_date=event.event_date)
        ]
        return items[:limit]


class DeepSearchRunner:
    def __init__(
        self,
        *,
        searxng_base_url: str,
        search_timeout: float = 90.0,
        results_limit: int = 80,
        pages_max: int = 4,
        query_suffix: str = "",
        max_events: int = 400,
        max_rounds: int = 8,
        batch_size: int = 30,
        catalog_budget: int = 150,
        catalog_max_links: int = 18,
        fetch_timeout: float = 25.0,
        fetch_concurrency: int = 6,
    ) -> None:
        self._searxng = SearXngSearchProvider(
            searxng_base_url,
            timeout=search_timeout,
            pages_max=pages_max,
        )
        self._results_limit = results_limit
        self._query_suffix = query_suffix.strip()
        self._max_events = max_events
        self._max_rounds = max_rounds
        self._batch_size = batch_size
        self._catalog_budget = catalog_budget
        self._engine = EnrichmentEngine(
            fetch_timeout=fetch_timeout,
            catalog_max_links=catalog_max_links,
        )
        self._fetch_concurrency = max(1, fetch_concurrency)

    async def aclose(self) -> None:
        await self._engine.aclose()

    def _build_query(self, user_query: str) -> str:
        query = user_query.strip()
        if self._query_suffix:
            query = f"{query} {self._query_suffix}".strip()
        return query

    async def run(
        self,
        user_query: str,
        *,
        on_progress: ProgressCallback | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> DeepSearchResult:
        built_query = self._build_query(user_query)
        progress = PipelineProgress(phase="search")
        result = DeepSearchResult(query=user_query, built_query=built_query, progress=progress)
        last_emit_at = 0.0

        async def emit(*, force: bool = False) -> None:
            nonlocal last_emit_at
            if not on_progress:
                return
            if not force and progress.phase == "enriching":
                now = time.monotonic()
                if progress.processed > 0 and progress.processed % 10 != 0:
                    if now - last_emit_at < 4.0:
                        return
                last_emit_at = now
            maybe = on_progress(progress)
            if asyncio.iscoroutine(maybe):
                await maybe

        await emit(force=True)

        try:
            raw_hits = await self._searxng.search(built_query, limit=self._results_limit)
        except Exception:
            logger.exception("SearXNG search failed for query=%r", built_query)
            raw_hits = []

        from event_search_bot.pipeline.catalog_feed import collect_trusted_catalog_hits

        catalog_hits = await collect_trusted_catalog_hits(built_query)

        merged: list[SearchResult] = []
        seen_urls: set[str] = set()

        def add_hits(items: list[SearchResult]) -> None:
            for item in items:
                key = item.link.rstrip("/")
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                merged.append(item)

        add_hits(rank_results(raw_hits, limit=self._results_limit))
        add_hits(catalog_hits)

        hits = rank_results(merged, limit=self._results_limit)
        progress.search_hits = len(hits)
        progress.phase = "enriching"

        ctx = EnrichmentContext(
            catalog_budget=self._catalog_budget,
            max_events_to_process=self._max_events,
        )

        for hit in hits:
            if is_cancelled and is_cancelled():
                ctx.cancelled = True
                break
            ctx.add_candidate(title=hit.title, url=hit.link, description=hit.snippet)

        progress.total_candidates = len(ctx.events)
        await emit(force=True)

        semaphore = asyncio.Semaphore(self._fetch_concurrency)

        for round_no in range(1, self._max_rounds + 1):
            if ctx.cancelled or (is_cancelled and is_cancelled()):
                ctx.cancelled = True
                break
            if ctx.processed_count >= ctx.max_events_to_process:
                break

            pending = [event for event in ctx.events if event.enrichment_status == "pending"]
            if not pending:
                break

            batch = pending[: self._batch_size]
            logger.info("Deep search round %s/%s: %s pending", round_no, self._max_rounds, len(batch))

            async def process_one(event: EventRecord) -> str:
                async with semaphore:
                    return await self._engine.process_event(event, ctx)

            tasks = [asyncio.create_task(process_one(event)) for event in batch]
            for finished in asyncio.as_completed(tasks):
                outcome = await finished
                progress.processed += 1
                if outcome == "enriched":
                    progress.enriched += 1
                elif outcome == "rejected":
                    progress.rejected += 1
                elif outcome == "failed":
                    progress.failed += 1

                progress.catalog_expanded = ctx.catalog_expanded
                progress.suitable_count = len(
                    [
                        e
                        for e in ctx.events
                        if e.relevance_status == "scored"
                        and (e.relevance_score or 0) >= get_scoring_rules().supplementary_borderline_min
                    ]
                )
                await emit()

        result.events = ctx.events
        result.progress = progress
        result.finished_at = datetime.now(timezone.utc)
        progress.phase = "completed"
        await emit(force=True)
        return result
