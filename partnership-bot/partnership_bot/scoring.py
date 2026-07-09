from __future__ import annotations

from typing import Any

MINSK_KEYWORDS = ("минск", "minsk", "беларус", "belarus")


def estimate_score(draft: dict[str, Any]) -> int:
    """Простая эвристика без обращения к внешнему сервису."""
    score = 20
    title = (draft.get("event_title") or "").lower()
    city = (draft.get("city") or "").lower()
    blob = f"{title} {city}"

    if any(word in blob for word in MINSK_KEYWORDS):
        score += 30

    if draft.get("event_url"):
        score += 15

    audience = draft.get("audience_range") or ""
    if audience == "2000+":
        score += 20
    elif audience == "500-2000":
        score += 12
    elif audience == "до 500":
        score += 5

    if draft.get("partnership_types"):
        score += 10

    fmt = draft.get("event_format") or ""
    if fmt in {"conference", "festival", "exhibition"}:
        score += 8

    return min(score, 100)
