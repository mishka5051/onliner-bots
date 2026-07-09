from __future__ import annotations

from event_search_bot.pipeline.filters import filter_scored_events
from event_search_bot.pipeline.jobs import DeepSearchJob, JobStatus
from event_search_bot.pipeline.models import EventRecord
from event_search_bot.pipeline.scoring_config import get_scoring_rules
from event_search_bot.search.models import SearchResult

MAX_MESSAGE_LEN = 4000


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _format_event_date(value) -> str:
    if value is None:
        return "дата неизвестна"
    try:
        return value.strftime("%d.%m.%Y")
    except Exception:
        return "дата неизвестна"


def format_result_item(index: int, result: SearchResult) -> str:
    title = _escape_html(_truncate(result.title, 120))
    domain = _escape_html(result.source_domain)
    lines = [f"<b>{index}. {title}</b>", f"🌐 {domain}"]

    if result.snippet:
        snippet = _escape_html(_truncate(result.snippet, 180))
        lines.append(snippet)

    lines.append(f'<a href="{result.link}">Открыть</a>')
    return "\n".join(lines)


def format_results_message(query: str, results: list[SearchResult]) -> list[str]:
    header = (
        f"🔍 <b>Быстрый поиск</b>\n"
        f"<b>Запрос:</b> {_escape_html(query)}\n"
        f"Найдено: <b>{len(results)}</b>\n"
    )

    if not results:
        return [
            header
            + "\nНичего подходящего не нашлось. Попробуйте уточнить запрос "
            "или запустите <b>Глубокий поиск</b>."
        ]

    chunks: list[str] = []
    current = header + "\n"
    index = 1

    for result in results:
        block = format_result_item(index, result) + "\n\n"
        index += 1
        if len(current) + len(block) > MAX_MESSAGE_LEN and current.strip():
            chunks.append(current.rstrip())
            current = block
        else:
            current += block

    if current.strip():
        chunks.append(current.rstrip())

    footer = (
        "\n\n<i>Для обогащения страниц, скоринга и отчёта — "
        "режим «Глубокий поиск».</i>"
    )
    if chunks:
        if len(chunks[-1]) + len(footer) <= MAX_MESSAGE_LEN:
            chunks[-1] += footer
        else:
            chunks.append(footer.lstrip())

    return chunks


def format_job_progress(job: DeepSearchJob) -> str:
    query = _escape_html(job.query)
    progress = job.progress
    phase_labels = {
        "starting": "запуск",
        "search": "поиск в SearXNG",
        "enriching": "обогащение и скоринг",
        "completed": "завершено",
    }
    phase = phase_labels.get(progress.phase, progress.phase)

    lines = [
        f"🔬 <b>Глубокий поиск</b> · <code>{job.job_id}</code>",
        f"<b>Запрос:</b> {query}",
        f"<b>Этап:</b> {phase}",
    ]
    if progress.phase == "search":
        lines.append("<i>+ каталоги tier A/B (it-event, bezkassira, …)</i>")

    if progress.search_hits:
        lines.append(f"Ссылок из поиска: <b>{progress.search_hits}</b>")
    if progress.total_candidates:
        lines.append(f"Кандидатов в очереди: <b>{progress.total_candidates}</b>")
    if progress.processed:
        lines.append(
            f"Обработано: <b>{progress.processed}</b> · "
            f"с оценкой: <b>{progress.enriched}</b> · "
            f"отклонено: <b>{progress.rejected}</b> · "
            f"ошибки: <b>{progress.failed}</b>"
        )
    if progress.catalog_expanded:
        lines.append(f"Из каталогов добавлено: <b>{progress.catalog_expanded}</b>")
    if progress.suitable_count:
        lines.append(f"Подходящих (оценка ≥ 25): <b>{progress.suitable_count}</b>")

    if job.status == JobStatus.QUEUED:
        lines.append("\n⏳ В очереди — скоро начну (один поиск за раз).")
    elif job.status == JobStatus.RUNNING:
        lines.append("\n🔄 Идёт обработка…")
        lines.append("<i>Можете пользоваться ботом — пришлю результат, когда закончу.</i>")

    return "\n".join(lines)


def format_deep_event_item(index: int, event: EventRecord) -> str:
    title = _escape_html(_truncate(event.title, 120))
    lines = [f"<b>{index}. {title}</b>"]

    meta: list[str] = []
    if event.relevance_score is not None:
        meta.append(f"⭐ {event.relevance_score}")
    if event.onliner_fit_score is not None:
        meta.append(f"Onliner {event.onliner_fit_score}")
    if event.is_minsk is True:
        meta.append("📍 Минск")
    elif event.is_minsk is False:
        meta.append("не Минск")
    if meta:
        lines.append(" · ".join(meta))

    lines.append(f"📅 {_format_event_date(event.event_date)}")
    if event.city:
        lines.append(f"🏙 {_escape_html(_truncate(event.city, 60))}")

    if event.partner_participation_possible:
        lines.append("🤝 признаки партнёрства")

    if event.relevance_score is not None and event.relevance_score >= 50 and event.is_minsk:
        from event_search_bot.pipeline.non_event import looks_like_real_event

        if looks_like_real_event(event_type=event.event_type, event_date=event.event_date):
            lines.append("✅ топ-кандидат для инфопартнёрства")

    lines.append(f'<a href="{event.url}">Открыть</a>')
    return "\n".join(lines)


def format_deep_results_summary(job: DeepSearchJob) -> list[str]:
    if job.result is None:
        return ["❌ Нет данных по заданию."]

    result = job.result
    progress = result.progress
    query = _escape_html(result.query)
    suitable = result.suitable_events()
    top = result.top_shortlist()

    header = (
        f"✅ <b>Глубокий поиск завершён</b>\n"
        f"<b>Запрос:</b> {query}\n"
        f"Обработано: <b>{progress.processed}</b> · "
        f"с оценкой: <b>{progress.enriched}</b> · "
        f"подходящих: <b>{len(suitable)}</b>\n"
    )

    if job.status == JobStatus.CANCELLED:
        header = header.replace("завершён", "остановлен") + "\n⚠️ Поиск остановлен пользователем.\n"
    if job.error:
        header += f"\n⚠️ {_escape_html(_truncate(job.error, 300))}\n"

    if not top:
        minsk_suitable = [e for e in suitable if e.is_minsk]
        if not minsk_suitable:
            return [
                header
                + "\nТоп-кандидатов для shortlist не найдено. "
                "Полный список — через «Выгрузку» с фильтрами."
            ]
        display = minsk_suitable[:8]
        header += "\n<i>Shortlist-кандидатов нет, показываю лучшие по оценке (Минск):</i>\n\n"
    else:
        display = top
        header += f"\n<b>Топ-{len(display)} для shortlist:</b>\n\n"

    chunks: list[str] = []
    current = header
    for index, event in enumerate(display, start=1):
        block = format_deep_event_item(index, event) + "\n\n"
        if len(current) + len(block) > MAX_MESSAGE_LEN and current.strip():
            chunks.append(current.rstrip())
            current = block
        else:
            current += block

    footer = (
        "\n\n📎 Выберите <b>Выгрузку</b> — настроите фильтры (Минск / score / партнёрство) "
        "и скачаете HTML или CSV.\n"
        "📊 <b>Аналитика</b> · 📇 <b>Карточки</b> · 📤 <b>Отправить коллеге</b> — кнопки ниже."
    )
    if current.strip():
        if len(current) + len(footer) <= MAX_MESSAGE_LEN:
            chunks.append((current + footer).rstrip())
        else:
            chunks.append(current.rstrip())
            chunks.append(footer.lstrip())
    elif not chunks:
        chunks.append(header + footer)

    return chunks


def format_jobs_list(jobs: list[DeepSearchJob]) -> str:
    if not jobs:
        return "📋 У вас пока нет заданий глубокого поиска."

    lines = ["📋 <b>Ваши задания</b>\n"]
    for job in reversed(jobs[-5:]):
        status_icon = {
            JobStatus.QUEUED: "⏳",
            JobStatus.RUNNING: "🔄",
            JobStatus.COMPLETED: "✅",
            JobStatus.FAILED: "❌",
            JobStatus.CANCELLED: "⏹",
        }.get(job.status, "•")
        query = _escape_html(_truncate(job.query, 50))
        status_label = {
            JobStatus.QUEUED: "в очереди",
            JobStatus.RUNNING: "в работе",
            JobStatus.COMPLETED: "готово",
            JobStatus.FAILED: "ошибка",
            JobStatus.CANCELLED: "остановлено",
        }.get(job.status, job.status.value)
        lines.append(f"{status_icon} <code>{job.job_id}</code> — {query}")
        if job.is_active():
            lines.append(
                f"   {status_label} · {job.progress.phase} · обработано {job.progress.processed}"
            )
    lines.append(
        "\n<i>ID задания или «статус» — в чат. Отмена: <code>отмена ID</code>. "
        "Кнопка «◀️ Назад» — в главное меню.</i>"
    )
    return "\n".join(lines)


def format_export_filters_prompt(job: DeepSearchJob) -> str:
    from event_search_bot.pipeline.jobs import get_export_filters

    filters = get_export_filters(job.job_id)
    return (
        f"📎 <b>Выгрузка отчёта</b> · <code>{job.job_id}</code>\n"
        f"<b>Запрос:</b> {_escape_html(job.query)}\n\n"
        "Включите фильтры — в CSV/HTML попадут только нужные строки:\n"
        f"• Только Минск — {'да' if filters.minsk_only else 'нет'}\n"
        f"• Score ≥ 50 — {'да' if filters.min_score_50 else 'нет'}\n"
        f"• Признаки партнёрства — {'да' if filters.partnership_only else 'нет'}\n\n"
        "<i>Нажмите фильтр для переключения, затем CSV или HTML.</i>"
    )


def format_event_card(event: EventRecord, index: int, total: int) -> str:
    rules = get_scoring_rules()
    title = _escape_html(_truncate(event.title, 140))
    lines = [
        f"📇 <b>Карточка {index + 1}/{total}</b>",
        f"<b>{title}</b>",
        "",
        f"⭐ <b>Оценка:</b> {event.relevance_score if event.relevance_score is not None else '—'}",
    ]
    if event.onliner_fit_score is not None:
        lines.append(f"Onliner fit: <b>{event.onliner_fit_score}</b>")

    breakdown = event.score_breakdown or {}
    if breakdown:
        lines.append("\n<b>Разбор баллов:</b>")
        for key, value in breakdown.items():
            if not value or value == 0:
                continue
            label = rules.score_labels.get(key, key)
            lines.append(f"• {_escape_html(label)}: <b>{value}</b>")

    lines.append(f"\n📅 {_format_event_date(event.event_date)}")
    if event.city:
        lines.append(f"🏙 {_escape_html(event.city)}")
    if event.is_minsk is True:
        lines.append("📍 Минск")
    elif event.is_minsk is False:
        lines.append("📍 не Минск")

    if event.partner_participation_possible:
        formats = ", ".join(event.partner_formats) if event.partner_formats else "да"
        lines.append(f"🤝 Партнёрство: {_escape_html(formats)}")

    if event.theme_tags:
        lines.append(f"🏷 {_escape_html(', '.join(event.theme_tags[:6]))}")

    lines.append(f"\n🔗 {_escape_html(event.url)}")
    return "\n".join(lines)


def format_event_list_prompt(job: DeepSearchJob, page: int, page_size: int = 5) -> str:
    if job.result is None:
        return "Нет данных по заданию."
    events = filter_scored_events(job.result.events)
    total = len(events)
    if not events:
        return (
            f"📇 <b>Карточки мероприятий</b> · <code>{job.job_id}</code>\n"
            "Нет событий с оценкой для карточек."
        )
    start = page * page_size
    end = min(start + page_size, total)
    lines = [
        f"📇 <b>Карточки мероприятий</b> · <code>{job.job_id}</code>",
        f"Показаны {start + 1}–{end} из {total}. Нажмите номер для деталей.",
    ]
    for offset, event in enumerate(events[start:end], start=start):
        score = event.relevance_score or "—"
        title = _escape_html(_truncate(event.title, 50))
        lines.append(f"\n<b>{offset + 1}.</b> {title} · ⭐ {score}")
    return "\n".join(lines)


def format_history_list(entries: list) -> str:
    from event_search_bot.storage.user_storage import HistoryEntry

    if not entries:
        return (
            "🕐 <b>История поисков</b>\n\n"
            "Пока пусто. После быстрого или глубокого поиска здесь появятся запросы "
            "с сохранённым результатом."
        )
    lines = ["🕐 <b>Последние поиски</b>\n"]
    for entry in entries:
        if not isinstance(entry, HistoryEntry):
            continue
        mode = "быстрый" if entry.mode == "quick" else "глубокий"
        query = _escape_html(_truncate(entry.query, 60))
        has_result = "✓" if entry.summary_text or entry.job_id else "·"
        lines.append(f"• [{mode}] {has_result} {query}")
    lines.append("\n<i>Нажмите запрос, чтобы открыть сохранённый результат.</i>")
    return "\n".join(lines)


def format_leads_dashboard(new_count: int, approved_count: int) -> str:
    return (
        "📥 <b>Заявки на инфопартнерство</b>\n\n"
        f"🆕 Новые: <b>{new_count}</b>\n"
        f"✅ Одобренные: <b>{approved_count}</b>\n\n"
        "<i>Выберите раздел ниже.</i>"
    )


def format_leads_list(section: str, items: list, page: int, total: int, page_size: int) -> str:
    from event_search_bot.partnership.models import ApprovedPartnershipEvent, PartnershipLead

    page_count = max(1, (total + page_size - 1) // page_size)
    title_map = {
        "new": "🆕 <b>Новые заявки</b>",
        "events": "✅ <b>Одобренные мероприятия</b>",
    }
    if not items:
        empty_map = {
            "new": "Новых заявок пока нет.",
            "events": "Одобренных мероприятий пока нет.",
        }
        return f"{title_map.get(section, '📥 <b>Заявки</b>')}\n\n{empty_map.get(section, 'Пока пусто.')}"

    lines = [
        title_map.get(section, "📥 <b>Заявки</b>"),
        f"<i>Страница {page + 1}/{page_count} · всего {total}</i>",
        "",
    ]
    for item in items:
        if isinstance(item, PartnershipLead):
            title = _escape_html(_truncate(item.event_title, 44))
            city = _escape_html(item.city or "—")
            score = f" · score {item.auto_score}" if item.auto_score is not None else ""
            lines.append(f"• <code>{item.short_id}</code> · {title}")
            lines.append(f"  {city}{score}")
        elif isinstance(item, ApprovedPartnershipEvent):
            title = _escape_html(_truncate(item.event_title, 44))
            city = _escape_html(item.city or "—")
            date = item.event_date.strftime("%d.%m.%Y") if item.event_date else "—"
            lines.append(f"• <code>{item.short_id}</code> · {title}")
            lines.append(f"  {city} · {date}")
    lines.append("\n<i>Откройте карточку кнопкой ниже.</i>")
    return "\n".join(lines)


def format_lead_card(lead) -> str:
    from event_search_bot.partnership.models import PartnershipLead

    if not isinstance(lead, PartnershipLead):
        return "Заявка не найдена."

    title = _escape_html(lead.event_title)
    lines = [
        f"📥 <b>Заявка</b> · <code>{lead.short_id}</code>",
        f"<b>Статус:</b> {lead.status}",
        f"<b>Мероприятие:</b> {title}",
    ]
    if lead.city:
        lines.append(f"🏙 {_escape_html(lead.city)}")
    if lead.event_date:
        lines.append(f"📅 {lead.event_date.strftime('%d.%m.%Y')}")
    if lead.auto_score is not None:
        lines.append(f"⭐ Оценка: <b>{lead.auto_score}</b>")
    if lead.partnership_types:
        lines.append(f"🤝 {_escape_html(', '.join(lead.partnership_types))}")
    contact = lead.contact_name or lead.contact_email or lead.contact_phone or ""
    if lead.telegram_username:
        contact = f"{contact} @{lead.telegram_username}".strip()
    if contact:
        lines.append(f"👤 {_escape_html(contact)}")
    if lead.comment:
        lines.append(f"\n💬 {_escape_html(_truncate(lead.comment, 400))}")
    if lead.event_url:
        lines.append(f"\n🔗 {_escape_html(lead.event_url)}")
    if lead.approved_at:
        lines.append(f"\n✅ Одобрено: {lead.approved_at.strftime('%d.%m.%Y %H:%M')}")
    if lead.deleted_at:
        lines.append(f"\n🗑 Удалено: {lead.deleted_at.strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)


def format_approved_event_card(event) -> str:
    from event_search_bot.partnership.models import ApprovedPartnershipEvent

    if not isinstance(event, ApprovedPartnershipEvent):
        return "Мероприятие не найдено."

    lines = [
        f"📅 <b>Одобренное мероприятие</b> · <code>{event.short_id}</code>",
        f"<b>Название:</b> {_escape_html(event.event_title)}",
    ]
    if event.city:
        lines.append(f"🏙 {_escape_html(event.city)}")
    if event.event_date:
        lines.append(f"📅 {event.event_date.strftime('%d.%m.%Y')}")
    lines.append(f"✅ Одобрено: {event.approved_at.strftime('%d.%m.%Y %H:%M')}")
    if event.event_url:
        lines.append(f"\n🔗 {_escape_html(event.event_url)}")
    return "\n".join(lines)


def format_new_lead_notification(lead) -> str:
    from event_search_bot.partnership.models import PartnershipLead

    if not isinstance(lead, PartnershipLead):
        return "Новая заявка"
    title = _escape_html(_truncate(lead.event_title, 80))
    return (
        "🆕 <b>Новая заявка</b> (partnership-бот)\n"
        f"<b>{title}</b>\n"
        f"Город: {_escape_html(lead.city or '—')}\n"
        "Откройте «📥 Заявки» в боте поиска."
    )
