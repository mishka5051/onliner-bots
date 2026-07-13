from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from event_search_bot.pipeline.candidate_gate import (
    MIN_QUERY_RELEVANCE,
    is_actionable_event_candidate,
    is_catalog_provenance_snippet,
    query_relevance_score,
)
from event_search_bot.pipeline.catalog import CatalogPageDetector
from event_search_bot.pipeline.catalog_links import CatalogLinkExtractor
from event_search_bot.pipeline.lead_time import LeadTimeValidator
from event_search_bot.pipeline.models import EventRecord, duplicate_key
from event_search_bot.pipeline.page_fetcher import FetchSkipped, HttpPageFetcher
from event_search_bot.pipeline.page_parser import EventPageParser
from event_search_bot.pipeline.scoring import EventScoringService
from event_search_bot.pipeline.scoring_config import ScoringRules, get_scoring_rules
from event_search_bot.pipeline.structured import StructuredEventExtractor
from event_search_bot.pipeline.text_sanitize import sanitize_page_text

logger = logging.getLogger(__name__)

CATALOG_NOTE = "Страница-каталог: не отдельное мероприятие"


@dataclass
class EnrichmentContext:
    user_query: str = ""
    events: list[EventRecord] = field(default_factory=list)
    seen_keys: set[str] = field(default_factory=set)
    catalog_budget: int = 150
    max_events_to_process: int = 400
    max_catalog_generation: int = 2
    processed_count: int = 0
    catalog_expanded: int = 0
    cancelled: bool = False

    def add_candidate(
        self,
        *,
        title: str,
        url: str,
        description: str | None = None,
        catalog_generation: int = 0,
    ) -> EventRecord | None:
        if self.user_query and not is_actionable_event_candidate(
            user_query=self.user_query,
            title=title,
            url=url,
        ):
            return None
        key = duplicate_key(url)
        if key in self.seen_keys:
            return None
        self.seen_keys.add(key)
        record = EventRecord.from_search_hit(
            title=title,
            url=url,
            description=description,
            catalog_generation=catalog_generation,
        )
        self.events.append(record)
        return record


class EnrichmentEngine:
    def __init__(
        self,
        *,
        rules: ScoringRules | None = None,
        fetch_timeout: float = 25.0,
        catalog_max_links: int = 18,
        soft_reject_minsk: bool = False,
    ) -> None:
        self._rules = rules or get_scoring_rules()
        self._fetcher = HttpPageFetcher(timeout=fetch_timeout)
        self._parser = EventPageParser(self._rules)
        self._structured = StructuredEventExtractor()
        self._catalog_detector = CatalogPageDetector()
        self._catalog_links = CatalogLinkExtractor(max_links=catalog_max_links)
        self._lead_time = LeadTimeValidator(self._rules)
        self._scoring = EventScoringService(self._rules)
        self._soft_reject_minsk = soft_reject_minsk

    async def aclose(self) -> None:
        await self._fetcher.aclose()

    async def process_event(self, event: EventRecord, ctx: EnrichmentContext) -> str:
        """Returns: enriched | rejected | failed | skipped."""
        if ctx.cancelled:
            return "skipped"
        if ctx.processed_count >= ctx.max_events_to_process:
            return "skipped"

        ctx.processed_count += 1

        try:
            page = await self._fetcher.fetch(
                event.url, title=event.title, snippet=event.description
            )
        except FetchSkipped as exc:
            if "каталог" in exc.reason.lower() or "служебная" in exc.reason.lower():
                self._reject(event, exc.reason)
                return "rejected"
            self._fail(event, exc.reason)
            return "failed"

        structured = self._structured.extract_best(page.html)

        if self._catalog_detector.is_catalog_page(
            url=event.url,
            title=event.title,
            html=page.html,
            page_text=page.text,
        ):
            expanded = self._expand_catalog(event, page.html, ctx)
            note = CATALOG_NOTE
            if expanded:
                note = f"{CATALOG_NOTE}; извлечено ссылок: {expanded}"
            self._reject(event, note)
            return "rejected"

        if self._catalog_detector.is_foreign_city_in_title(event.title):
            if "минск" not in event.title.lower() and "minsk" not in event.title.lower():
                self._reject(event, "Мероприятие не в Минске/Беларуси (по названию)")
                return "rejected"

        parsed = self._parser.parse(
            title=event.title,
            page_text=page.text,
            snippet=event.description,
            html=page.html,
            url=event.url,
            structured=structured,
        )

        if parsed.minsk_confidence == "unlikely" and not self._soft_reject_minsk:
            self._reject(event, "Мероприятие не относится к Минску/Беларуси")
            return "rejected"

        relevance = query_relevance_score(
            ctx.user_query,
            title=event.title,
            url=event.url,
            page_text=page.text,
        )
        if ctx.user_query and relevance < MIN_QUERY_RELEVANCE:
            self._reject(event, f"Слабое совпадение с запросом ({relevance}%)")
            return "rejected"

        self._apply_parsed(event, page, parsed)
        event.score_breakdown = {
            **(event.score_breakdown or {}),
            "query_relevance": relevance,
        }
        self._score(event)
        return "enriched"

    def _expand_catalog(self, event: EventRecord, html: str, ctx: EnrichmentContext) -> int:
        if ctx.catalog_budget <= 0:
            return 0
        if event.catalog_generation >= ctx.max_catalog_generation:
            return 0

        links = self._catalog_links.extract(html, event.url)
        if not links:
            return 0

        links = links[: ctx.catalog_budget]
        created = 0
        child_description = None if is_catalog_provenance_snippet(event.description) else event.description
        for link in links:
            if ctx.cancelled:
                break
            new_event = ctx.add_candidate(
                title=link.title,
                url=link.url,
                description=child_description,
                catalog_generation=event.catalog_generation + 1,
            )
            if new_event is not None:
                created += 1
                ctx.catalog_budget -= 1
                ctx.catalog_expanded += 1
        return created

    def _apply_parsed(self, event: EventRecord, page, parsed) -> None:
        lead_time_days, enough_lead_time = self._lead_time.evaluate(parsed.event_date)

        event.city = parsed.city or event.city
        event.event_date = parsed.event_date or event.event_date
        event.is_minsk = parsed.is_minsk
        event.estimated_attendance = parsed.estimated_attendance
        event.event_type = parsed.event_type
        event.theme_tags = parsed.theme_tags
        event.is_free = parsed.is_free
        event.is_recurring = parsed.is_recurring
        event.partner_participation_possible = parsed.partner_participation_possible
        event.partner_formats = parsed.partner_formats
        event.page_text = sanitize_page_text(page.text)
        event.page_fetch_error = None
        event.lead_time_days = lead_time_days
        event.is_enough_lead_time = enough_lead_time
        event.enrichment_status = "completed"
        event.enriched_at = datetime.now(timezone.utc)

        if parsed.minsk_confidence == "uncertain":
            event.page_fetch_error = "Город не подтверждён — нужна ручная проверка"

        if parsed.extraction_sources:
            event.score_breakdown = {
                **(event.score_breakdown or {}),
                "extraction_sources": parsed.extraction_sources,
                "minsk_confidence": parsed.minsk_confidence,
            }

    def _score(self, event: EventRecord) -> None:
        if event.enrichment_status != "completed":
            return

        result = self._scoring.score(event)
        event.relevance_score = result.relevance_score
        event.onliner_fit_score = result.onliner_fit_score
        event.score_breakdown = {**(event.score_breakdown or {}), **result.score_breakdown}
        event.score_explanations = result.score_explanations
        event.relevance_status = "scored"

        if result.relevance_score < self._rules.auto_reject_below:
            event.relevance_status = "rejected"

    def _reject(self, event: EventRecord, note: str) -> None:
        event.enrichment_status = "completed"
        event.relevance_status = "rejected"
        event.is_minsk = False
        event.page_fetch_error = note
        event.enriched_at = datetime.now(timezone.utc)

    def _fail(self, event: EventRecord, error: str) -> None:
        event.enrichment_status = "failed"
        event.page_fetch_error = error[:1000]
        event.enriched_at = datetime.now(timezone.utc)
