"""Lightweight ranking for quick search snippets."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from event_search_bot.pipeline.candidate_gate import extract_query_tokens, is_actionable_event_candidate
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
    "конференц-зал",
    "конференц зал",
    "конференцзал",
    "переговорная",
    "переговорные комнаты",
    "аренда зала",
    "аренда конференц",
    "аренда площадки",
    "снять зал",
    "почасовая аренда",
    "hourly rental",
    "conference room rental",
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

NON_EVENT_PATH_MARKERS = (
    "/arenda",
    "/rent",
    "/conference-hall",
    "/coworking",
    "/banket",
    "/uslugi",
    "/services",
)


def _text_blob(result: SearchResult) -> str:
    parts = [result.title, result.snippet or "", result.link, result.source_domain]
    return " ".join(parts).lower()


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def _query_match_hits(result: SearchResult, query_tokens: list[str]) -> int:
    if not query_tokens:
        return 0
    text = _text_blob(result)
    return sum(1 for token in query_tokens if token in text)


def score_result(result: SearchResult) -> int:
    text = _text_blob(result)
    score = 0

    score += min(30, _keyword_hits(text, EVENT_KEYWORDS) * 10)
    score += min(20, _keyword_hits(text, MINSK_KEYWORDS) * 10)
    score += min(15, _keyword_hits(text, PARTNERSHIP_KEYWORDS) * 8)

    path = urlparse(result.link).path.lower()
    if any(marker in path for marker in GUIDE_PATH_MARKERS):
        score -= 15
    if any(marker in path for marker in NON_EVENT_PATH_MARKERS):
        score -= 45
    if any(keyword in text for keyword in NON_EVENT_KEYWORDS):
        score -= 40

    if re.search(r"\b20(1[0-9]|2[0-3])\b", text):
        score -= 10

    return score


def is_blocked(result: SearchResult) -> bool:
    domain = result.source_domain
    if domain in BLOCKED_DOMAINS:
        return True
    return any(domain.endswith(f".{blocked}") for blocked in BLOCKED_DOMAINS)


def rank_results(results: list[SearchResult], *, limit: int, query: str | None = None) -> list[SearchResult]:
    filtered = [item for item in results if not is_blocked(item)]
    if query:
        gated = [
            item
            for item in filtered
            if is_actionable_event_candidate(
                user_query=query,
                title=item.title,
                url=item.link,
            )
        ]
        if gated:
            filtered = gated

    query_tokens = extract_query_tokens(query or "")
    if query_tokens:
        query_filtered: list[SearchResult] = []
        for item in filtered:
            hits = _query_match_hits(item, query_tokens)
            if len(query_tokens) >= 2 and hits < 1:
                continue
            if len(query_tokens) >= 4 and hits < 2:
                continue
            query_filtered.append(item)
        # Do not return an empty list just because query tokens were too strict.
        if query_filtered:
            filtered = query_filtered

    scored = [(item, score_result(item)) for item in filtered]
    # Hard-cut obvious non-event and low-relevance pages.
    strong = [(item, score) for item, score in scored if score >= 12]
    positive = [(item, score) for item, score in scored if score > 0]
    # Fallback order:
    # 1) strong event-like results
    # 2) positive-score results
    # 3) if everything is weak/negative, still return best-ranked items
    #    so deep search can process something instead of zero hits.
    pool = strong if strong else (positive if positive else scored)
    ranked = sorted(pool, key=lambda pair: pair[1], reverse=True)
    return [
        SearchResult(
            title=item.title,
            snippet=item.snippet,
            link=item.link,
            source_domain=item.source_domain,
            relevance_hint=score,
        )
        for item, score in ranked[:limit]
    ]
