from __future__ import annotations

from event_search_bot.config import get_settings


def staff_user_ids() -> set[int]:
    raw = get_settings().allowed_telegram_ids.strip()
    if not raw:
        return set()
    result: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            result.add(int(part))
    return result


def is_staff(user_id: int) -> bool:
    ids = staff_user_ids()
    if not ids:
        return True
    return user_id in ids
