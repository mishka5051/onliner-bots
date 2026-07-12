"""Единый фильтр кандидатов: событие по запросу, не навигация и не каталог."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from event_search_bot.pipeline.catalog import CatalogPageDetector
from event_search_bot.pipeline.trusted_catalogs import (
    GENERIC_TITLE_PATTERNS,
    QUERY_STOPWORDS,
    is_skipped_catalog_child_url,
)

MIN_TOKEN_LEN = 2
MIN_QUERY_RELEVANCE = 30

EVENT_SIGNAL_KEYWORDS = (
    "конференц",
    "форум",
    "саммит",
    "митап",
    "выставк",
    "expo",
    "festival",
    "фестив",
    "мероприят",
    "conference",
    "summit",
    "event",
)

NAV_TITLE_PATTERNS = (
    re.compile(r"^по\s+(тематикам|странам|направлениям)", re.IGNORECASE),
    re.compile(r"^как\s+пользов", re.IGNORECASE),
    re.compile(r"^(январь|февраль|март|апрель|май|июнь|июля|август|сентябрь|октябрь|ноябрь|декабрь)\s+20\d{2}$", re.IGNORECASE),
    re.compile(r"^выставки\s+по\s+", re.IGNORECASE),
    re.compile(r"^конференции\s+по\s+", re.IGNORECASE),
)

CATALOG_SNIPPET_PREFIX = "Каталог "

_catalog_detector = CatalogPageDetector()


def extract_query_tokens(query: str) -> list[str]:
    raw = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]{2,}", (query or "").lower())
    seen: set[str] = set()
    tokens: list[str] = []
    for token in raw:
        if token in QUERY_STOPWORDS or token in seen:
            continue
        if len(token) < MIN_TOKEN_LEN:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def is_catalog_provenance_snippet(snippet: str | None) -> bool:
    return bool(snippet and snippet.startswith(CATALOG_SNIPPET_PREFIX))


def _text_blob(*parts: str | None) -> str:
    return " ".join(part for part in parts if part).lower()


def _has_event_signal(title: str, url: str) -> bool:
    blob = _text_blob(title, url)
    return any(keyword in blob for keyword in EVENT_SIGNAL_KEYWORDS)


def _navigation_title(title: str) -> bool:
    normalized = (title or "").strip()
    if not normalized:
        return True
    if any(pattern.search(normalized) for pattern in NAV_TITLE_PATTERNS):
        return True
    if any(pattern.search(normalized.lower()) for pattern in GENERIC_TITLE_PATTERNS):
        return True
    return False


def query_relevance_score(
    user_query: str,
    *,
    title: str,
    url: str,
    page_text: str | None = None,
) -> int:
    tokens = extract_query_tokens(user_query)
    if not tokens:
        return 50
    blob = _text_blob(title, url, (page_text or "")[:6000])
    hits = sum(1 for token in tokens if token in blob)
    if hits == 0:
        return 0
    return min(100, int(round(100 * hits / len(tokens))))


def is_actionable_event_candidate(
    *,
    user_query: str,
    title: str,
    url: str,
    tier: str | None = None,
) -> bool:
    """True — URL похож на карточку одного мероприятия и релевантен запросу."""
    if not url or not title:
        return False

    if is_skipped_catalog_child_url(url):
        return False

    if _navigation_title(title):
        return False

    if _catalog_detector.is_catalog_search_result(url=url, title=title):
        return False

    tokens = extract_query_tokens(user_query)
    blob = _text_blob(title, url)

    if tokens:
        if not any(token in blob for token in tokens):
            return False
    else:
        if not _has_event_signal(title, url):
            return False

    if tier == "B":
        minsk_markers = ("минск", "minsk", "беларус", "belarus", " рб", "by/")
        has_geo = any(marker in blob for marker in minsk_markers)
        query_has_geo = any(marker.strip() in user_query.lower() for marker in minsk_markers)
        if not has_geo and not query_has_geo:
            return False

    path = urlparse(url).path.lower()
    if path.count("/") <= 2 and not _has_event_signal(title, url):
        return False

    return True
