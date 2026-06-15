import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.application.ports.page_fetcher import PageFetcherPort
from app.core.exceptions import EventNotFoundError
from app.domain.enums import EnrichmentStatus, RelevanceStatus
from app.domain.services.catalog_page_detector import CatalogPageDetector
from app.domain.services.deduplication import DeduplicationService
from app.domain.services.lead_time_validator import LeadTimeValidator
from app.domain.services.recurrence_detector import RecurrenceDetector
from app.infrastructure.db.repositories import EventCandidateRepository
from app.infrastructure.enrichment.catalog_link_extractor import CatalogLinkExtractor
from app.infrastructure.enrichment.page_parser import EventPageParser
from app.infrastructure.enrichment.supplementary_search import SupplementarySearchService
from app.infrastructure.enrichment.text_sanitize import sanitize_page_text

logger = logging.getLogger(__name__)

CATALOG_NOTE = "Страница-каталог: не отдельное мероприятие"


class EnrichEventUseCase:
    def __init__(
        self,
        event_repository: EventCandidateRepository,
        page_fetcher: PageFetcherPort,
        deduplication_service: DeduplicationService,
        *,
        page_parser: EventPageParser | None = None,
        supplementary_search: SupplementarySearchService | None = None,
        lead_time_validator: LeadTimeValidator | None = None,
        recurrence_detector: RecurrenceDetector | None = None,
        catalog_detector: CatalogPageDetector | None = None,
        catalog_link_extractor: CatalogLinkExtractor | None = None,
    ) -> None:
        self._events = event_repository
        self._page_fetcher = page_fetcher
        self._deduplication = deduplication_service
        self._page_parser = page_parser or EventPageParser()
        self._supplementary_search = supplementary_search
        self._lead_time = lead_time_validator or LeadTimeValidator()
        self._recurrence = recurrence_detector or RecurrenceDetector()
        self._catalog_detector = catalog_detector or CatalogPageDetector()
        self._catalog_links = catalog_link_extractor or CatalogLinkExtractor()

    async def enrich_event(self, event_id: uuid.UUID) -> None:
        event = await self._events.get_by_id(event_id)
        if event is None:
            raise EventNotFoundError(message="Event not found", details={"event_id": str(event_id)})

        if self._catalog_detector.is_catalog_search_result(
            url=event.url,
            title=event.title,
            snippet=event.description,
        ):
            await self._reject_catalog(event_id, CATALOG_NOTE)
            return

        try:
            page = await self._page_fetcher.fetch(event.url)
            if self._catalog_detector.is_catalog_page(
                url=event.url,
                title=event.title,
                html=page.html,
                page_text=page.text,
            ):
                expanded = await self._expand_catalog(event, page.html)
                note = CATALOG_NOTE
                if expanded:
                    note = f"{CATALOG_NOTE}; извлечено ссылок: {expanded}"
                await self._reject_catalog(event_id, note)
                return

            if self._catalog_detector.is_foreign_city_in_title(event.title):
                await self._reject_catalog(event_id, "Мероприятие не в Минске/Беларуси (по названию)")
                return

            extra_text = ""
            trend_score = 0
            if self._supplementary_search is not None:
                extra_text, mentions = await self._supplementary_search.collect_context(event.title)
                trend_score = min(100, mentions * 10)

            page_text = "\n\n".join(filter(None, [page.text, extra_text]))
            parsed = self._page_parser.parse(
                title=event.title,
                page_text=page_text,
                snippet=event.description,
                html=page.html,
                url=event.url,
            )

            if not parsed.is_minsk:
                await self._reject_catalog(event_id, "Мероприятие не относится к Минску")
                return

            async with self._events.nested_transaction():
                event = await self._events.get_by_id(event_id)
                if event is None:
                    return

                parent_key = self._recurrence.build_parent_event_key(event.title, event.source_domain)
                previous = await self._events.find_by_parent_event_key(parent_key, exclude_id=event.id)
                is_recurring = parsed.is_recurring or previous is not None
                estimated_attendance = parsed.estimated_attendance
                attendance_source = "parsed" if parsed.estimated_attendance else None
                if previous and previous.estimated_attendance:
                    estimated_attendance = previous.estimated_attendance
                    attendance_source = "historical"

                event_date = parsed.event_date or event.event_date
                lead_time_days, enough_lead_time = self._lead_time.evaluate(event_date)

                event.city = parsed.city or event.city
                event.event_date = event_date
                event.is_minsk = parsed.is_minsk
                event.estimated_attendance = estimated_attendance
                event.attendance_source = attendance_source
                event.event_type = parsed.event_type
                event.theme_tags = parsed.theme_tags
                event.is_free = parsed.is_free
                event.ticket_info = parsed.ticket_info
                event.is_recurring = is_recurring
                event.edition_label = parsed.edition_label
                event.parent_event_key = parent_key
                event.partner_participation_possible = parsed.partner_participation_possible
                event.partner_formats = parsed.partner_formats
                event.organizer_benefits = parsed.organizer_benefits
                event.trend_score = trend_score
                event.page_text = sanitize_page_text(page_text)
                event.page_fetch_error = None
                event.lead_time_days = lead_time_days
                event.is_enough_lead_time = enough_lead_time
                event.enrichment_status = EnrichmentStatus.COMPLETED.value
                event.enriched_at = datetime.now(timezone.utc)
                event.updated_at = datetime.now(timezone.utc)
                await self._events.save_enrichment(event)
            await self._events.commit()
        except Exception as exc:
            logger.exception("Enrichment failed for event %s", event_id)
            failed = await self._events.get_by_id(event_id)
            if failed is not None:
                failed.enrichment_status = EnrichmentStatus.FAILED.value
                failed.page_fetch_error = str(exc)[:1000]
                failed.enriched_at = datetime.now(timezone.utc)
                failed.updated_at = datetime.now(timezone.utc)
                await self._events.save_enrichment(failed)
                await self._events.commit()

    async def _expand_catalog(self, event, html: str) -> int:
        links = self._catalog_links.extract(html, event.url)
        created = 0
        for link in links:
            duplicate_key = self._deduplication.compute_duplicate_key(link.url)
            existing = await self._events.get_by_duplicate_key(duplicate_key)
            if existing is not None:
                continue
            await self._events.create(
                title=link.title,
                description=event.description,
                url=link.url,
                source_domain=urlparse(link.url).netloc.lower().removeprefix("www."),
                source_query=event.source_query,
                search_run_id=event.search_run_id,
                duplicate_key=duplicate_key,
                category=event.category,
            )
            created += 1
        if created:
            await self._events.commit()
            logger.info("Expanded catalog %s into %s event links", event.url, created)
        return created

    async def _reject_catalog(self, event_id: uuid.UUID, note: str) -> None:
        event = await self._events.get_by_id(event_id)
        if event is None:
            return
        event.enrichment_status = EnrichmentStatus.COMPLETED.value
        event.relevance_status = RelevanceStatus.REJECTED.value
        event.is_minsk = False
        event.page_fetch_error = note
        event.enriched_at = datetime.now(timezone.utc)
        event.updated_at = datetime.now(timezone.utc)
        await self._events.save_enrichment(event)
        await self._events.commit()

    async def enrich_pending_for_run(self, search_run_id: uuid.UUID) -> int:
        pending = await self._events.list_by_search_run(
            search_run_id,
            enrichment_status=EnrichmentStatus.PENDING.value,
        )
        enriched_count = 0
        for event in pending:
            try:
                await self.enrich_event(event.id)
                enriched_count += 1
            except Exception:
                continue
        return enriched_count
