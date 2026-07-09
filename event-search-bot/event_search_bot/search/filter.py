"""Lightweight ranking for quick search snippets."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from event_search_bot.search.models import SearchResult

EVENT_KEYWORDS = (
    "мероприят",
    "конференц",
    "форум",
    "фестив",
    "выставк",
    "концерт",
    "митап",
    "саммит",
    "expo",
    "afisha",
    "афиш",
    "билет",
    "event",
    "conference",
    "summit",
    "festival",
)

MINSK_KEYWORDS = ("минск", "minsk", "беларус", "belarus", "рб")

PARTNERSHIP_KEYWORDS = (
    "инфопартн",
    "партнёр",
    "партнер",
    "спонсор",
    "media partner",
    "info partner",
)

BLOCKED_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "tiktok.com",
    "t.me",
    "vk.com",
    "ok.ru",
    "wikipedia.org",
}

CATALOG_DOMAINS = {
    "expomap.ru",
    "all-events.ru",
    "it-event.by",
    "bezkassira.by",
    "conference.by",
    "ict2go.ru",
    "events.by",
    "afisha.ru",
    "timepad.ru",
    "entrance.by",
    "relax.by",
}

NON_EVENT_KEYWORDS = (
    "коворкинг",
    "coworking",
    "свадьб",
    "wedding",
    "арендовать помещение",
    "аренда офис",
    "банкетный",
    "организация мероприятий",
    "alocasia",
    "plantaddicts",
    "gardenia.net",
)

GUIDE_PATH_MARKERS = (
    "/blog/",
    "/article/",
    "/news/",
    "/help/",
    "/guide/",
    "gajd",
    "гайд",
)


def _text_blob(result: SearchResult) -> str:
    parts = [result.title, result.snippet or "", result.link, result.source_domain]
    return " ".join(parts).lower()


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def score_result(result: SearchResult) -> int:
    text = _text_blob(result)
    score = 0

    score += min(30, _keyword_hits(text, EVENT_KEYWORDS) * 10)
    score += min(20, _keyword_hits(text, MINSK_KEYWORDS) * 10)
    score += min(15, _keyword_hits(text, PARTNERSHIP_KEYWORDS) * 8)

    path = urlparse(result.link).path.lower()
    if any(marker in path for marker in GUIDE_PATH_MARKERS):
        score -= 15
    if any(keyword in text for keyword in NON_EVENT_KEYWORDS):
        score -= 40
    if result.source_domain in CATALOG_DOMAINS:
        score += 25
        if _keyword_hits(text, EVENT_KEYWORDS) > 0:
            score += 10

    if re.search(r"\b20(1[0-9]|2[0-3])\b", text):
        score -= 10

    return score


def is_blocked(result: SearchResult) -> bool:
    domain = result.source_domain
    if domain in BLOCKED_DOMAINS:
        return True
    return any(domain.endswith(f".{blocked}") for blocked in BLOCKED_DOMAINS)


def rank_results(results: list[SearchResult], *, limit: int) -> list[SearchResult]:
    filtered = [item for item in results if not is_blocked(item)]
    ranked = sorted(
        filtered,
        key=lambda item: score_result(item),
        reverse=True,
    )
    return [
        SearchResult(
            title=item.title,
            snippet=item.snippet,
            link=item.link,
            source_domain=item.source_domain,
            relevance_hint=score_result(item),
        )
        for item in ranked[:limit]
    ]
