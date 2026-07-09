"""Проверенные каталоги мероприятий в Минске/Беларуси."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

QUERY_STOPWORDS = frozenset(
    {
        "и",
        "в",
        "на",
        "по",
        "для",
        "the",
        "and",
        "or",
        "конференция",
        "конференции",
        "мероприятия",
        "мероприятие",
        "форум",
        "минск",
        "minsk",
        "беларус",
        "belarus",
        "2025",
        "2026",
        "2027",
    }
)

MINSK_MARKERS = ("минск", "minsk", "беларус", "belarus", " рб", "by/")


@dataclass(frozen=True)
class TrustedCatalog:
    name: str
    url: str
    domain: str
    tier: str  # "A" | "B"


TIER_A: tuple[TrustedCatalog, ...] = (
    TrustedCatalog("IT-event.by", "https://it-event.by/events2026/", "it-event.by", "A"),
    TrustedCatalog(
        "BezKassira IT Минск",
        "https://bezkassira.by/events/it_i_internet-minsk/conference/",
        "bezkassira.by",
        "A",
    ),
    TrustedCatalog("ICT2GO Минск", "https://ict2go.ru/regions/Minsk/", "ict2go.ru", "A"),
    TrustedCatalog(
        "All-Events Минск",
        "https://all-events.ru/events/calendar/city-is-minsk/",
        "all-events.ru",
        "A",
    ),
    TrustedCatalog(
        "Expomap IT Минск",
        "https://expomap.ru/conference/theme/it-i-tsifrovye-tehnologii/city/minsk/",
        "expomap.ru",
        "A",
    ),
)

TIER_B: tuple[TrustedCatalog, ...] = (
    TrustedCatalog("Conference.by", "https://conference.by/", "conference.by", "B"),
    TrustedCatalog(
        "Workspace Digital BY",
        "https://workspace.ru/events/?country=belarus",
        "workspace.ru",
        "B",
    ),
    TrustedCatalog(
        "BezKassira бизнес Минск",
        "https://bezkassira.by/events/biznes-minsk/conference/",
        "bezkassira.by",
        "B",
    ),
    TrustedCatalog(
        "Expomap Беларусь",
        "https://expomap.ru/conference/country/belarus/",
        "expomap.ru",
        "B",
    ),
)

SKIP_URL_PARTS = (
    "/ploshadki",
    "/kategorija",
    "/category",
    "/categories",
    "/news/",
    "/novosti/",
    "/blog/",
    "/article/",
    "/help/",
    "/login",
    "/register",
    "/cart",
    "/search",
    "/events/filter/",
    "/events/calendar/",
    "/organizatoram/",
    "/regions/",
)

SKIP_URL_REGEX = (
    re.compile(r"/events/[a-z0-9_]+-minsk/?$", re.IGNORECASE),
    re.compile(r"/events/[a-z0-9_]+-belarus/?$", re.IGNORECASE),
    re.compile(r"/events/[^/]+/conference/?$", re.IGNORECASE),
)

GENERIC_TITLE_PATTERNS = (
    re.compile(r"^для\s+", re.IGNORECASE),
    re.compile(r"^другое( событие)?$", re.IGNORECASE),
    re.compile(r"^ит и интернет$", re.IGNORECASE),
    re.compile(r"^красота и здоровье$", re.IGNORECASE),
    re.compile(r"^сертификаты$", re.IGNORECASE),
    re.compile(r"^бизнес$", re.IGNORECASE),
)


def _query_tokens(query: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]{3,}", query.lower())
    return [token for token in tokens if token not in QUERY_STOPWORDS]


def _text_blob(*parts: str | None) -> str:
    return " ".join(part for part in parts if part).lower()


def is_skipped_catalog_child_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    if any(marker in path for marker in SKIP_URL_PARTS):
        return True
    return any(pattern.search(path) for pattern in SKIP_URL_REGEX)


def event_matches_query(
    *,
    user_query: str,
    title: str,
    url: str,
    tier: str,
) -> bool:
    if is_skipped_catalog_child_url(url):
        return False
    normalized_title = (title or "").strip().lower()
    if any(pattern.search(normalized_title) for pattern in GENERIC_TITLE_PATTERNS):
        return False

    blob = _text_blob(title, url)
    tokens = _query_tokens(user_query)
    if not tokens:
        return True

    matched = sum(1 for token in tokens if token in blob)
    if matched == 0:
        return False

    if tier == "B":
        has_geo = any(marker in blob for marker in MINSK_MARKERS)
        query_has_geo = any(marker.strip() in user_query.lower() for marker in MINSK_MARKERS)
        if not has_geo and not query_has_geo:
            return False
        if matched < 2 and not has_geo:
            return False

    return True


def all_trusted_catalogs() -> list[TrustedCatalog]:
    return [*TIER_A, *TIER_B]
