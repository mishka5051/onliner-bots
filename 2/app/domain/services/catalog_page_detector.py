import re
from urllib.parse import urlparse

DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf")

CATALOG_PATH_MARKERS = (
    "/events/calendar",
    "/city-is-",
    "/conference/city/",
    "/regions/",
    "/kalendar/",
    "/kalendar_",
    "/exhibitions/all",
    "/country-city/",
    "/dates/future",
    "/events2026",
    "/meropriyatiya/",
    "/vystavki/",
)

CATALOG_PATH_REGEX = (
    re.compile(r"/calendar(?:/|$)", re.IGNORECASE),
    re.compile(r"/city/[^/]+/\d*/?$", re.IGNORECASE),
)

EVENTS_CATEGORY_PATH = re.compile(r"/events/([^/]+)/?$", re.IGNORECASE)

TITLE_CATALOG_PHRASES = (
    "каталог",
    "календарь выставок",
    "календарь мероприятий",
    "расписание выставок",
    "расписание мероприятий",
    "афиша мероприятий",
    "мероприятия в минске",
    "конференции в минске",
    "выставки в минске",
    "выставки в беларуси",
    "список конференций",
    "все выставки",
    "инфопартнеров",
    "инфопартнёров",
)

GENERIC_TITLE = re.compile(
    r"^(выставки|мероприятия|конференции|календарь(?:\s+выставок)?|расписание(?:\s+выставок)?)\s*(\d{4})?\s*\.{0,3}$",
    re.IGNORECASE,
)

JSON_LD_EVENT = re.compile(
    r'"@type"\s*:\s*"[^"]*event[^"]*"',
    re.IGNORECASE,
)

OTHER_CITY_IN_TITLE = re.compile(
    r"\b(москва|moscow|санкт-петербург|spb|петербург|казань|новосибирск)\b",
    re.IGNORECASE,
)


class CatalogPageDetector:
    def is_document_url(self, url: str) -> bool:
        return urlparse(url).path.lower().endswith(DOCUMENT_EXTENSIONS)

    def is_catalog_search_result(
        self,
        *,
        url: str,
        title: str,
        snippet: str | None = None,
    ) -> bool:
        if self.is_document_url(url):
            return True
        if self._url_looks_like_catalog(url):
            return True
        return self._title_looks_like_catalog(title, snippet)

    def is_catalog_page(
        self,
        *,
        url: str,
        title: str,
        html: str | None = None,
        page_text: str | None = None,
    ) -> bool:
        if self.is_catalog_search_result(url=url, title=title):
            return True
        if html and self._html_looks_like_catalog(html):
            return True
        if page_text and self._text_looks_like_listing(page_text):
            return True
        return False

    def is_foreign_city_in_title(self, title: str) -> bool:
        return bool(OTHER_CITY_IN_TITLE.search(title))

    def _url_looks_like_catalog(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        if not path or path == "/":
            return False

        for marker in CATALOG_PATH_MARKERS:
            if marker in path:
                return True

        for pattern in CATALOG_PATH_REGEX:
            if pattern.search(path):
                return True

        events_match = EVENTS_CATEGORY_PATH.search(path)
        if events_match and self._looks_like_events_category_slug(events_match.group(1)):
            return True

        return False

    def _looks_like_events_category_slug(self, slug: str) -> bool:
        lowered = slug.lower()
        if lowered in {"biznes", "minsk", "afisha", "calendar", "all", "list"}:
            return True
        return len(lowered) <= 12 and lowered.count("-") <= 1

    def _title_looks_like_catalog(self, title: str, snippet: str | None) -> bool:
        combined = f"{title} {snippet or ''}".lower().strip()
        if GENERIC_TITLE.match(title.strip()):
            return True
        return any(phrase in combined for phrase in TITLE_CATALOG_PHRASES)

    def _html_looks_like_catalog(self, html: str) -> bool:
        event_nodes = len(JSON_LD_EVENT.findall(html))
        if event_nodes >= 3:
            return True

        lowered = html.lower()
        if lowered.count("<time") >= 4:
            return True

        listing_markers = (
            "class=\"event-list",
            "class='event-list",
            "class=\"events-list",
            "class='events-list",
            "itemtype=\"http://schema.org/event",
        )
        marker_hits = sum(1 for marker in listing_markers if marker in lowered)
        return marker_hits >= 2 and event_nodes >= 2

    def _text_looks_like_listing(self, page_text: str) -> bool:
        year_dates = re.findall(r"\b\d{1,2}[./]\d{1,2}[./]20\d{2}\b", page_text)
        ru_dates = re.findall(
            r"\b\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+20\d{2}\b",
            page_text,
            flags=re.IGNORECASE,
        )
        unique_dates = len(set(year_dates + ru_dates))
        event_mentions = len(
            re.findall(r"(?:конференц|форум|выставк|мероприят|саммит)", page_text, re.IGNORECASE)
        )
        return unique_dates >= 5 and event_mentions >= 8
