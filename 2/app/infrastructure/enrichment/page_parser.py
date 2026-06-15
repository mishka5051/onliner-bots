import re
from dataclasses import dataclass
from datetime import datetime

from app.core.scoring_config import ScoringRules, get_scoring_rules
from app.domain.services.catalog_page_detector import CatalogPageDetector
from app.domain.services.event_type_classifier import EventTypeClassifier
from app.domain.services.minsk_detector import MinskDetector
from app.domain.services.recurrence_detector import RecurrenceDetector
from app.infrastructure.enrichment.html_metadata_extractor import (
    extract_event_date_from_html,
    extract_header_text,
)


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


class EventPageParser:
    DATE_PATTERNS = [
        re.compile(r"(\d{1,2})[./](\d{1,2})[./](20\d{2})"),
        re.compile(r"(20\d{2})-(\d{2})-(\d{2})"),
    ]
    CITY_PATTERN = re.compile(
        r"(?i)(?:г\.?|город)\s*(Минск|Minsk)|\b(Минск|Minsk)\b",
    )

    def __init__(self, rules: ScoringRules | None = None) -> None:
        self._rules = rules or get_scoring_rules()
        self._type_classifier = EventTypeClassifier(self._rules)
        self._minsk_detector = MinskDetector(self._rules)
        self._recurrence_detector = RecurrenceDetector()
        self._catalog_detector = CatalogPageDetector()

    def parse(
        self,
        *,
        title: str,
        page_text: str,
        snippet: str | None = None,
        html: str | None = None,
        url: str | None = None,
    ) -> ParsedEventPage:
        header_text = extract_header_text(html) if html else ""
        combined = "\n".join(filter(None, [title, snippet, header_text, page_text]))
        lowered = combined.lower()

        city = self._extract_city(combined)
        event_date = self._extract_date(combined)
        if event_date is None and html:
            event_date = extract_event_date_from_html(html)
        attendance = self._extract_attendance(lowered)
        is_free, ticket_info = self._extract_ticket_info(lowered)
        partner_possible, partner_formats = self._extract_partner_info(lowered)
        theme_tags = self._extract_theme_tags(lowered)
        edition_label = self._recurrence_detector.detect_edition_label(title)
        is_recurring = self._recurrence_detector.looks_recurring(title, page_text)
        event_type = self._type_classifier.classify(title, page_text, snippet)
        organizer_benefits = self._extract_organizer_benefits(page_text)
        is_catalog = self._catalog_detector.is_catalog_page(
            url=url or "",
            title=title,
            page_text=page_text if not html else None,
            html=html,
        )
        is_minsk = self._minsk_detector.is_minsk(
            city=city,
            country="Беларусь",
            text=combined,
            title=title,
            is_catalog=is_catalog,
        )

        return ParsedEventPage(
            city=city,
            event_date=event_date,
            estimated_attendance=attendance,
            is_free=is_free,
            ticket_info=ticket_info,
            event_type=event_type,
            theme_tags=theme_tags,
            is_recurring=is_recurring,
            edition_label=edition_label,
            partner_participation_possible=partner_possible,
            partner_formats=partner_formats,
            organizer_benefits=organizer_benefits,
            is_minsk=is_minsk,
        )

    def _extract_city(self, text: str) -> str | None:
        match = self.CITY_PATTERN.search(text)
        if not match:
            return None
        return next(group for group in match.groups() if group)

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

    def _extract_ticket_info(self, lowered: str) -> tuple[bool | None, str | None]:
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

    def _extract_theme_tags(self, lowered: str) -> list[str]:
        tags: list[str] = []
        for theme, keywords in self._rules.onliner_theme_keywords.items():
            if any(keyword.lower() in lowered for keyword in keywords):
                tags.append(theme)
        return tags

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
