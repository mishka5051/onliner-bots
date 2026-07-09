from __future__ import annotations

import re

NON_EVENT_PATTERNS = (
    re.compile(r"коворкинг|coworking", re.IGNORECASE),
    re.compile(r"свадьб|wedding|бракосочетан", re.IGNORECASE),
    re.compile(r"ресторан\s+для\s+свадьб", re.IGNORECASE),
    re.compile(r"банкетн", re.IGNORECASE),
    re.compile(r"аренд[аы].{0,30}(помещен|офис|зал|площад)", re.IGNORECASE),
    re.compile(r"организац\w+\s+мероприятий", re.IGNORECASE),
    re.compile(r"event\s*agency|event\s*organizer", re.IGNORECASE),
    re.compile(r"под\s+ключ.{0,40}(агентств|компани|услуг)", re.IGNORECASE),
    re.compile(r"арендовать\s+помещение", re.IGNORECASE),
)


def is_non_event_page(*texts: str | None) -> bool:
    combined = " ".join(text for text in texts if text).strip()
    if not combined:
        return False
    return any(pattern.search(combined) for pattern in NON_EVENT_PATTERNS)


def looks_like_real_event(*, event_type: str | None, event_date) -> bool:
    if event_date is not None:
        return True
    return bool(event_type and event_type != "other")
