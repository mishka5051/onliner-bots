import re
from dataclasses import dataclass
from datetime import datetime

from event_search_bot.pipeline.catalog import CatalogPageDetector
from event_search_bot.pipeline.event_type import EventTypeClassifier
from event_search_bot.pipeline.html_meta import extract_event_date_from_html, extract_header_text
from event_search_bot.pipeline.minsk_detector import MinskDetector
from event_search_bot.pipeline.recurrence import RecurrenceDetector
from event_search_bot.pipeline.scoring_config import ScoringRules, get_scoring_rules
from event_search_bot.pipeline.structured import StructuredEventData
from event_search_bot.pipeline.theme_matcher import ThemeMatcherService


@dataclass(frozen=True)
class ParsedEventPage:
    city: str | None
    event_date: datetime | None
    estimated_attendance: int | None
    is_free: bool | None
    ticket_info: str | None
    event_type: str
    theme_tags: list[str]
    is_recurring: bool
    edition_label: str | None
    partner_participation_possible: bool
    partner_formats: list[str]
    organizer_benefits: str | None
    is_minsk: bool
    minsk_confidence: str
    extraction_sources: list[str]


class EventPageParser:
    DATE_PATTERNS = [
        re.compile(r"(\d{1,2})[./](\d{1,2})[./](20\d{2})"),
        re.compile(r"(20\d{2})-(\d{2})-(\d{2})"),
    ]
    CITY_PATTERN = re.compile(
        r"(?i)(?:г\.?|город)\s*([А-Яа-яA-Za-zёЁ\-\s]{2,40})"
        r"|\b(Минск|Minsk|Гомель|Витебск|Гродно|Брест|Могилёв|Mogilev)\b",
    )

    def __init__(
        self,
        rules: ScoringRules | None = None,
        *,
        theme_matcher: ThemeMatcherService | None = None,
    ) -> None:
        self._rules = rules or get_scoring_rules()
        self._type_classifier = EventTypeClassifier(self._rules)
        self._minsk_detector = MinskDetector(self._rules)
        self._recurrence_detector = RecurrenceDetector()
        self._catalog_detector = CatalogPageDetector()
        self._theme_matcher = theme_matcher or ThemeMatcherService(self._rules)

    def parse(
        self,
        *,
        title: str,
        page_text: str,
        snippet: str | None = None,
        html: str | None = None,
        url: str | None = None,
        structured: StructuredEventData | None = None,
    ) -> ParsedEventPage:
        sources: list[str] = []
        header_text = extract_header_text(html) if html else ""
        combined = "\n".join(filter(None, [title, snippet, header_text, page_text]))
        lowered = combined.lower()

        city = self._extract_city(combined)
        event_date = self._extract_date(combined)
        if event_date is None and html:
            event_date = extract_event_date_from_html(html)
            if event_date:
                sources.append("html-meta")

        if structured:
            if structured.city and not city:
                city = structured.city
                sources.append("json-ld:city")
            if structured.start_date and not event_date:
                event_date = structured.start_date
                sources.append("json-ld:date")
            if structured.name and len(structured.name) > len(title):
                title = structured.name
                sources.append("json-ld:name")

        attendance = self._sanitize_attendance(self._extract_attendance(lowered))
        is_free, ticket_info = self._extract_ticket_info(lowered)
        if structured and structured.is_free is not None and is_free is None:
            is_free = structured.is_free
            ticket_info = "json-ld"
            sources.append("json-ld:free")

        partner_possible, partner_formats = self._extract_partner_info(lowered)
        _, theme_tags = self._theme_matcher.compute_fit_score(combined)
        if theme_tags:
            sources.append("theme-matcher")

        edition_label = self._recurrence_detector.detect_edition_label(title)
        is_recurring = self._recurrence_detector.looks_recurring(title, page_text)
        event_type = structured.event_type_hint if structured and structured.event_type_hint else None
        if not event_type:
            event_type = self._type_classifier.classify(title, page_text, snippet)

        organizer_benefits = self._extract_organizer_benefits(page_text)
        if structured and structured.organizer and not organizer_benefits:
            organizer_benefits = structured.organizer
            sources.append("json-ld:organizer")

        is_catalog = self._catalog_detector.is_catalog_page(
            url=url or "",
            title=title,
            page_text=page_text if not html else None,
            html=html,
        )
        minsk_confidence = self._minsk_detector.evaluate(
            city=city,
            country=structured.country if structured else None,
            text=combined,
            title=title,
            is_catalog=is_catalog,
        )
        is_minsk = minsk_confidence in {"confirmed", "likely"}

        return ParsedEventPage(
            city=city,
            event_date=event_date,
            estimated_attendance=attendance,
            is_free=is_free,
            ticket_info=ticket_info,
            event_type=event_type or "other",
            theme_tags=theme_tags,
            is_recurring=is_recurring,
            edition_label=edition_label,
            partner_participation_possible=partner_possible,
            partner_formats=partner_formats,
            organizer_benefits=organizer_benefits,
            is_minsk=is_minsk,
            minsk_confidence=minsk_confidence,
            extraction_sources=sources,
        )

    def _extract_city(self, text: str) -> str | None:
        match = self.CITY_PATTERN.search(text)
        if not match:
            return None
        city = next((group for group in match.groups() if group), None)
        if city is None:
            return None
        return city.strip().strip(",.")

    def _extract_date(self, text: str) -> datetime | None:
        for pattern in self.DATE_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            groups = match.groups()
            try:
                if len(groups) == 3 and groups[0].startswith("20"):
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                day, month, year = (int(groups[0]), int(groups[1]), int(groups[2]))
                return datetime(year, month, day)
            except ValueError:
                continue
        return None

    def _extract_attendance(self, lowered: str) -> int | None:
        for pattern in self._rules.attendance_patterns:
            match = re.search(pattern, lowered, flags=re.IGNORECASE)
            if not match:
                continue
            digits = re.sub(r"\s+", "", match.group(1))
            try:
                return int(digits)
            except ValueError:
                continue
        return None

    def _sanitize_attendance(self, value: int | None) -> int | None:
        if value is None or value <= 0:
            return None
        if value > 100_000:
            return None
        return value

    def _extract_ticket_info(self, lowered: str) -> tuple[bool | None, str | None]:
        if any(phrase in lowered for phrase in self._rules.free_false_positive_phrases):
            return None, "ambiguous_free"

        if any(keyword in lowered for keyword in self._rules.free_keywords):
            return True, "free"
        if any(keyword in lowered for keyword in self._rules.paid_keywords):
            return False, "paid"
        return None, None

    def _extract_partner_info(self, lowered: str) -> tuple[bool, list[str]]:
        formats: list[str] = []
        if any(keyword in lowered for keyword in self._rules.partner_keywords):
            formats.append("partnership")
        if "стенд" in lowered or "exhibitor" in lowered:
            formats.append("booth")
        if "инфопартн" in lowered or "медиапартн" in lowered:
            formats.append("media")
        return bool(formats), formats

    def _extract_organizer_benefits(self, page_text: str) -> str | None:
        lowered = page_text.lower()
        markers = ("партнёрам", "партнерам", "спонсорам", "сотрудничеств")
        for marker in markers:
            index = lowered.find(marker)
            if index == -1:
                continue
            snippet = page_text[index : index + 500].strip()
            return snippet
        return None
