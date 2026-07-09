from __future__ import annotations

import csv
import html
import io
from datetime import datetime

from event_search_bot.pipeline.filters import ExportFilters, apply_export_filters, filter_scored_events
from event_search_bot.pipeline.models import EventRecord
from event_search_bot.pipeline.runner import DeepSearchResult


def _events_for_export(result: DeepSearchResult, filters: ExportFilters | None) -> list[EventRecord]:
    base = filter_scored_events(result.events)
    if filters is None:
        return result.suitable_events()
    return apply_export_filters(base, filters)


def _fmt_date(value: datetime | None) -> str:
    if value is None:
        return ""
    try:
        return value.strftime("%d.%m.%Y")
    except Exception:
        return ""


def build_csv_report(result: DeepSearchResult, filters: ExportFilters | None = None) -> bytes:
    suitable = _events_for_export(result, filters)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "№",
            "Название",
            "Дата",
            "Город",
            "Минск",
            "Оценка",
            "Onliner fit",
            "Партнёрство",
            "Тип",
            "Темы",
            "URL",
            "Заметки",
        ]
    )
    for index, event in enumerate(suitable, start=1):
        writer.writerow(
            [
                index,
                event.title,
                _fmt_date(event.event_date),
                event.city or "",
                "да" if event.is_minsk else ("нет" if event.is_minsk is False else ""),
                event.relevance_score or "",
                event.onliner_fit_score or "",
                "да" if event.partner_participation_possible else "",
                event.event_type,
                ", ".join(event.theme_tags),
                event.url,
                event.page_fetch_error or "",
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def build_html_report(result: DeepSearchResult, filters: ExportFilters | None = None) -> bytes:
    suitable = _events_for_export(result, filters)
    top = [event for event in result.top_shortlist() if event in suitable]
    progress = result.progress
    query = html.escape(result.query)
    built = html.escape(result.built_query)

    rows = []
    for index, event in enumerate(suitable, start=1):
        score = event.relevance_score or "—"
        city = html.escape(event.city or "—")
        title = html.escape(event.title)
        url = html.escape(event.url, quote=True)
        date = _fmt_date(event.event_date) or "—"
        minsk = "✓" if event.is_minsk else ("✗" if event.is_minsk is False else "?")
        partner = "✓" if event.partner_participation_possible else ""
        themes = html.escape(", ".join(event.theme_tags))
        highlight = ' class="top"' if event in top else ""
        rows.append(
            f"<tr{highlight}><td>{index}</td><td><a href=\"{url}\">{title}</a></td>"
            f"<td>{date}</td><td>{city}</td><td>{minsk}</td><td><b>{score}</b></td>"
            f"<td>{partner}</td><td>{themes}</td></tr>"
        )

    body_rows = "\n".join(rows) if rows else "<tr><td colspan='8'>Подходящих мероприятий не найдено</td></tr>"

    filter_note = ""
    if filters is not None and filters.label() != "без фильтров":
        filter_note = f"<p><b>Фильтры отчёта:</b> {html.escape(filters.label())}</p>"

    document = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Глубокий поиск: {query}</title>
<style>
body {{ font-family:Segoe UI,system-ui,sans-serif; margin:2rem; color:#1a1a2e; background:#f8f9fc; }}
h1 {{ color:#16213e; }}
.meta {{ background:#fff; padding:1rem 1.25rem; border-radius:12px; margin-bottom:1.5rem; box-shadow:0 2px 8px rgba(0,0,0,.06); }}
table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.06); }}
th, td {{ padding:.65rem .75rem; text-align:left; border-bottom:1px solid #eef0f5; font-size:14px; }}
th {{ background:#16213e; color:#fff; }}
tr.top {{ background:#e8f5e9; }}
tr:hover {{ background:#f0f4ff; }}
</style>
</head>
<body>
<h1>🔬 Глубокий поиск мероприятий</h1>
<div class="meta">
<p><b>Запрос:</b> {query}</p>
<p><b>Поисковый запрос:</b> {built}</p>
<p>Найдено ссылок: <b>{progress.search_hits}</b> · Обработано: <b>{progress.processed}</b> ·
С оценкой: <b>{progress.enriched}</b> · В отчёте: <b>{len(suitable)}</b></p>
{filter_note}
<p><i>Зелёным выделены топ-кандидаты для shortlist (Минск, оценка ≥ 50).</i></p>
</div>
<table>
<thead><tr><th>#</th><th>Название</th><th>Дата</th><th>Город</th><th>Минск</th><th>Оценка</th><th>Партнёрство</th><th>Темы</th></tr></thead>
<tbody>
{body_rows}
</tbody>
</table>
</body>
</html>"""
    return document.encode("utf-8")
