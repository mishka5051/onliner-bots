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
MIN_QUERY_RELEVANCE = 25

THEME_SYNONYMS: dict[str, tuple[str, ...]] = {
    "it": (
        "ит",
        "tech",
        "digital",
        "devops",
        "software",
        "разработ",
        "developer",
        "программ",
        "митап",
        "meetup",
        "hackathon",
        "devconf",
        "python",
        "javascript",
        "frontend",
        "backend",
        "стартап",
        "startup",
        "кибер",
        "cyber",
        "data",
        "cloud",
        "product",
        "ux",
        "ui",
    ),
    "expo": (
        "выставк",
        "expo",
        "exhibition",
        "trade show",
        "ярмарк",
        "fair",
        "salon",
    ),
    "business": (
        "бизнес",
        "business",
        "enterprise",
        "corporate",
        "предприним",
        "ceo",
        "маркетинг",
        "marketing",
    ),
}

IT_EVENT_NAME_HINTS = (
    "productcamp",
    "tibo",
    "it space",
    "it-space",
    "itspace",
    "devconf",
    "highload",
    "gamejam",
    "barcamp",
    "pycon",
    "jsconf",
)

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


def detect_query_themes(tokens: list[str]) -> set[str]:
    themes: set[str] = set()
    for token in tokens:
        if token in ("it", "ит"):
            themes.add("it")
        if token in ("expo", "exhibition", "ярмарк"):
            themes.add("expo")
        if token in ("business", "бизнес", "маркетинг", "marketing"):
            themes.add("business")
    return themes


def expanded_match_tokens(user_query: str) -> tuple[list[str], list[str]]:
    strict = extract_query_tokens(user_query)
    expanded: list[str] = []
    seen: set[str] = set()
    for token in strict:
        if token not in seen:
            expanded.append(token)
            seen.add(token)
    for theme in detect_query_themes(strict):
        for synonym in THEME_SYNONYMS.get(theme, ()):
            if synonym not in seen:
                expanded.append(synonym)
                seen.add(synonym)
    return strict, expanded


def _matches_query_intent(
    blob: str,
    *,
    title: str,
    url: str,
    user_query: str,
    source: str = "search",
) -> bool:
    strict, expanded = expanded_match_tokens(user_query)
    if not strict and not expanded:
        return _has_event_signal(title, url)

    if any(token in blob for token in strict):
        return True

    if detect_query_themes(strict) & {"it"} and any(hint in blob for hint in IT_EVENT_NAME_HINTS):
        return True

    soft_hits = sum(1 for token in expanded if token not in strict and token in blob)
    if soft_hits >= 2 and _has_event_signal(title, url):
        return True
    if soft_hits >= 1 and _has_event_signal(title, url) and any(
        marker in blob for marker in ("минск", "minsk", "беларус", "belarus")
    ):
        return True
    if source == "catalog" and (_has_event_signal(title, url) or _looks_like_event_detail_url(url)):
        return True
    return False


def is_catalog_provenance_snippet(snippet: str | None) -> bool:
    return bool(snippet and snippet.startswith(CATALOG_SNIPPET_PREFIX))


def _text_blob(*parts: str | None) -> str:
    return " ".join(part for part in parts if part).lower()


def _has_event_signal(title: str, url: str) -> bool:
    blob = _text_blob(title, url)
    return any(keyword in blob for keyword in EVENT_SIGNAL_KEYWORDS)


def _looks_like_event_detail_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    if re.search(r"/20\d{2}(?:[/-]|$)", path):
        return True
    return path.count("/") >= 3 and not path.endswith(("/expo/", "/conference/", "/events/"))


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
    strict, expanded = expanded_match_tokens(user_query)
    if not strict and not expanded:
        return 50
    blob = _text_blob(title, url, (page_text or "")[:6000])
    strict_hits = sum(1 for token in strict if token in blob)
    if strict_hits:
        return min(100, int(round(100 * strict_hits / max(1, len(strict)))))
    expanded_hits = sum(1 for token in expanded if token not in strict and token in blob)
    if detect_query_themes(strict) & {"it"} and any(hint in blob for hint in IT_EVENT_NAME_HINTS):
        return max(35, 20 + 10 * expanded_hits)
    if expanded_hits >= 2:
        return min(85, 25 + 12 * expanded_hits)
    if expanded_hits == 1:
        return 28
    return 0


def is_actionable_event_candidate(
    *,
    user_query: str,
    title: str,
    url: str,
    tier: str | None = None,
    source: str = "search",
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

    blob = _text_blob(title, url)
    if not _matches_query_intent(blob, title=title, url=url, user_query=user_query, source=source):
        return False

    strict, _ = expanded_match_tokens(user_query)
    known_it = bool(
        detect_query_themes(strict) & {"it"} and any(hint in blob for hint in IT_EVENT_NAME_HINTS)
    )

    if tier == "B":
        minsk_markers = ("минск", "minsk", "беларус", "belarus", " рб", "by/")
        has_geo = any(marker in blob for marker in minsk_markers)
        query_has_geo = any(marker.strip() in user_query.lower() for marker in minsk_markers)
        if not has_geo and not query_has_geo:
            return False

    path = urlparse(url).path.lower()
    if path.count("/") <= 2 and not _has_event_signal(title, url) and not known_it:
        return False

    return True
