from __future__ import annotations

from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

from event_search_bot.pipeline.filters import ExportFilters, apply_export_filters, filter_scored_events
from event_search_bot.pipeline.runner import DeepSearchResult


def _month_key(event_date: datetime | None) -> str:
    if event_date is None:
        return "дата неизвестна"
    return event_date.strftime("%Y-%m")


def build_analytics_text(result: DeepSearchResult, filters: ExportFilters) -> str:
    events = apply_export_filters(filter_scored_events(result.events), filters)
    if not events:
        return "📊 <b>Аналитика</b>\n\nНет событий для анализа с выбранными фильтрами."

    by_theme: Counter[str] = Counter()
    by_month: Counter[str] = Counter()
    by_domain: Counter[str] = Counter()

    for event in events:
        themes = event.theme_tags or ["без темы"]
        for theme in themes:
            by_theme[theme] += 1
        by_month[_month_key(event.event_date)] += 1
        domain = event.source_domain or urlparse(event.url).netloc.lower().removeprefix("www.")
        if domain:
            by_domain[domain] += 1

    lines = [
        "📊 <b>Аналитика инфопартнёрств</b>",
        f"<b>Запрос:</b> {result.query}",
        f"<b>Фильтры:</b> {filters.label()}",
        f"<b>Событий в выборке:</b> {len(events)}",
        "",
        "<b>По темам</b>",
    ]
    for theme, count in by_theme.most_common(8):
        lines.append(f"• {theme}: {count}")

    lines.append("\n<b>По месяцам</b>")
    for month, count in sorted(by_month.items()):
        lines.append(f"• {month}: {count}")

    lines.append("\n<b>Топ источники (домены)</b>")
    for domain, count in by_domain.most_common(8):
        lines.append(f"• {domain}: {count}")

    minsk = sum(1 for event in events if event.is_minsk)
    partner = sum(1 for event in events if event.partner_participation_possible)
    high = sum(1 for event in events if (event.relevance_score or 0) >= 50)
    lines.append(
        f"\n<b>Сводка:</b> Минск {minsk} · score≥50: {high} · с партнёрством: {partner}"
    )
    return "\n".join(lines)


def build_share_summary(result: DeepSearchResult, filters: ExportFilters, limit: int = 8) -> str:
    events = apply_export_filters(filter_scored_events(result.events), filters)[:limit]
    lines = [
        f"🔬 Поиск: {result.query}",
        f"Подходящих: {len(apply_export_filters(filter_scored_events(result.events), filters))}",
        "",
    ]
    for index, event in enumerate(events, start=1):
        score = event.relevance_score or "—"
        date = event.event_date.strftime("%d.%m.%Y") if event.event_date else "?"
        city = event.city or "?"
        lines.append(f"{index}. {event.title} ({score} б., {city}, {date})")
        lines.append(event.url)
    lines.append("\n— Onliner Event Search Bot")
    return "\n".join(lines)
