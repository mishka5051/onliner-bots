from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.types import BufferedInputFile, CallbackQuery

from event_search_bot.bot.access import is_staff
from event_search_bot.bot.formatters import (
    format_event_card,
    format_event_list_prompt,
    format_export_filters_prompt,
    format_approved_event_card,
    format_history_list,
    format_lead_card,
    format_leads_dashboard,
    format_leads_list,
)
from event_search_bot.bot.keyboards import (
    MODE_DEEP,
    MODE_QUICK,
    approved_event_card_keyboard,
    QUERY_TEMPLATES,
    event_card_keyboard,
    event_list_keyboard,
    export_filters_keyboard,
    history_keyboard,
    history_view_keyboard,
    job_complete_keyboard,
    lead_card_keyboard,
    leads_dashboard_keyboard,
    leads_list_keyboard,
    main_menu_keyboard,
    sub_screen_keyboard,
)
from event_search_bot.bot.navigation import show_user_screen, track_extra_message
from event_search_bot.partnership.models import ApprovedPartnershipEvent, PartnershipLead
from event_search_bot.partnership.reader import get_lead_reader
from event_search_bot.pipeline.analytics import build_analytics_text, build_share_summary
from event_search_bot.storage.user_storage import user_storage
from event_search_bot.pipeline.filters import filter_scored_events
from event_search_bot.pipeline.jobs import get_export_filters, job_manager, report_files

logger = logging.getLogger(__name__)

callbacks_router = Router()

_leads_cache: dict[str, PartnershipLead] = {}
_approved_events_cache: dict[str, ApprovedPartnershipEvent] = {}


def _cache_leads(leads: list[PartnershipLead]) -> None:
    for lead in leads:
        _leads_cache[lead.short_id] = lead


def _cache_approved_events(events: list[ApprovedPartnershipEvent]) -> None:
    for event in events:
        _approved_events_cache[event.short_id] = event


def _counts(reader) -> tuple[int, int]:
    return (
        reader.count_leads("new"),
        reader.count_approved_events(),
    )


def _section_payload(reader, section: str, page: int, page_size: int = 5) -> tuple[str, object]:
    offset = page * page_size
    if section == "events":
        items = reader.list_approved_events(limit=page_size, offset=offset)
        total = reader.count_approved_events()
        _cache_approved_events(items)
    else:
        items = reader.list_leads(status="new", limit=page_size, offset=offset)
        total = reader.count_leads("new")
        _cache_leads(items)
    text = format_leads_list(section, items, page, total, page_size)
    markup = leads_list_keyboard(section, items, page, total, page_size)
    return text, markup


async def open_leads_dashboard(
    bot: Bot,
    *,
    user_id: int,
    chat_id: int,
    user_message=None,
) -> bool:
    from event_search_bot.bot.navigation import replace_screen

    reader = get_lead_reader()
    if not reader.is_available():
        return False
    user_storage.add_lead_watcher(user_id)
    new_count, approved_count = _counts(reader)
    await replace_screen(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=format_leads_dashboard(new_count, approved_count),
        inline_markup=leads_dashboard_keyboard(new_count, approved_count),
        reply_markup=main_menu_keyboard(user_id),
        user_message=user_message,
    )
    return True


async def open_leads_section(
    bot: Bot,
    *,
    user_id: int,
    chat_id: int,
    section: str,
    page: int = 0,
    user_message=None,
) -> bool:
    from event_search_bot.bot.navigation import replace_screen

    reader = get_lead_reader()
    if not reader.is_available():
        return False
    user_storage.add_lead_watcher(user_id)
    text, markup = _section_payload(reader, section, page)
    await replace_screen(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=text,
        inline_markup=markup,
        reply_markup=main_menu_keyboard(user_id),
        user_message=user_message,
    )
    return True


async def _show_callback_screen(
    callback: CallbackQuery,
    *,
    text: str,
    inline_markup=None,
    reply_markup=None,
) -> None:
    if not callback.from_user or not callback.message:
        return
    await show_user_screen(
        callback.bot,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        text=text,
        inline_markup=inline_markup,
        reply_markup=reply_markup or sub_screen_keyboard(callback.from_user.id),
        callback_message=callback.message,
    )


async def _track_sent(bot: Bot, user_id: int, message) -> None:
    if message is not None:
        track_extra_message(user_id, message.chat.id, message.message_id)


def _job_events(job):
    if job is None or job.result is None:
        return []
    return filter_scored_events(job.result.events)


@callbacks_router.callback_query(F.data.startswith("tpl:"))
async def on_query_template(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        return
    mode, key = parts[1], parts[2]
    query = QUERY_TEMPLATES.get(key)
    if not query:
        return

    from event_search_bot.bot.handlers import _run_quick_search, _start_deep_search

    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    if mode == MODE_DEEP:
        await _start_deep_search(callback.message, query, bot, user_id=user_id, chat_id=chat_id)
    else:
        await _run_quick_search(callback.message, query, user_id=user_id, chat_id=chat_id)


@callbacks_router.callback_query(F.data.startswith("hist:"))
async def on_history_action(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not callback.message:
        return
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    data = callback.data or ""

    if data == "hist:clear":
        user_storage.clear_history(user_id)
        await callback.answer("История очищена")
        entries = user_storage.list_history(user_id)
        await show_user_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=format_history_list(entries),
            inline_markup=history_keyboard(entries),
            reply_markup=sub_screen_keyboard(user_id),
            callback_message=callback.message,
        )
        return

    if data == "hist:list":
        await callback.answer()
        entries = user_storage.list_history(user_id)
        await show_user_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=format_history_list(entries),
            inline_markup=history_keyboard(entries),
            reply_markup=sub_screen_keyboard(user_id),
            callback_message=callback.message,
        )
        return

    parts = data.split(":", 2)
    if len(parts) < 2:
        return
    action = parts[1]

    if action == "rerun_job" and len(parts) == 3:
        job_id = parts[2]
        job = job_manager.get_job(job_id)
        if job is None:
            await callback.answer("Результат устарел", show_alert=True)
            return
        from event_search_bot.bot.handlers import _start_deep_search

        await callback.answer("Повторяю…")
        await _start_deep_search(callback.message, job.query, bot, user_id=user_id, chat_id=chat_id)
        return

    if action in {"view", "rerun"} and len(parts) == 3:
        try:
            entry_id = int(parts[2])
        except ValueError:
            return
        entry = user_storage.get_search(user_id, entry_id)
        if entry is None:
            await callback.answer("Запись не найдена", show_alert=True)
            return

        if action == "rerun":
            from event_search_bot.bot.handlers import _run_quick_search, _start_deep_search

            await callback.answer("Повторяю…")
            if entry.mode == MODE_DEEP:
                await _start_deep_search(callback.message, entry.query, bot, user_id=user_id, chat_id=chat_id)
            else:
                await _run_quick_search(callback.message, entry.query, user_id=user_id, chat_id=chat_id)
            return

        await callback.answer()
        text: str | None = None
        markup = history_view_keyboard(entry_id)
        if entry.job_id:
            job = job_manager.get_job(entry.job_id)
            if job is not None and job.result is not None:
                from event_search_bot.bot.formatters import format_deep_results_summary

                chunks = format_deep_results_summary(job)
                text = chunks[0]
                markup = job_complete_keyboard(entry.job_id)
        if text is None and entry.summary_text:
            text = entry.summary_text[:3900]
        if text is None:
            text = (
                f"🕐 <b>{'Глубокий' if entry.mode == MODE_DEEP else 'Быстрый'} поиск</b>\n\n"
                f"<b>Запрос:</b> {entry.query}\n\n"
                "Сохранённый результат недоступен (бот перезапускался). "
                "Нажмите «Повторить поиск»."
            )
        await show_user_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=text,
            inline_markup=markup,
            reply_markup=sub_screen_keyboard(user_id),
            callback_message=callback.message,
        )


@callbacks_router.callback_query(F.data == "leads:refresh")
async def on_leads_refresh(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        return
    if not is_staff(callback.from_user.id):
        await callback.answer("Доступ только для сотрудников", show_alert=True)
        return
    await callback.answer()
    user_storage.add_lead_watcher(callback.from_user.id)
    reader = get_lead_reader()
    if not reader.is_available():
        await _show_callback_screen(
            callback,
            text="📥 База заявок недоступна. Проверьте общий volume с partnership-bot.",
        )
        return
    new_count, approved_count = _counts(reader)
    await show_user_screen(
        callback.bot,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        text=format_leads_dashboard(new_count, approved_count),
        inline_markup=leads_dashboard_keyboard(new_count, approved_count),
        reply_markup=main_menu_keyboard(callback.from_user.id),
        callback_message=callback.message,
    )


@callbacks_router.callback_query(F.data == "leads:home")
async def on_leads_home(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        return
    await callback.answer()
    from event_search_bot.bot.handlers import _show_main_menu

    await _show_main_menu(
        callback.bot,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
    )


@callbacks_router.callback_query(F.data.startswith("ls:"))
async def on_leads_section(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        return
    if not is_staff(callback.from_user.id):
        await callback.answer("Доступ только для сотрудников", show_alert=True)
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        return
    _, section, page_raw = parts
    try:
        page = max(0, int(page_raw))
    except ValueError:
        page = 0
    user_storage.add_lead_watcher(callback.from_user.id)
    reader = get_lead_reader()
    if not reader.is_available():
        await callback.answer("База заявок недоступна", show_alert=True)
        return
    await callback.answer()
    text, markup = _section_payload(reader, section, page)
    await show_user_screen(
        callback.bot,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        text=text,
        inline_markup=markup,
        reply_markup=main_menu_keyboard(callback.from_user.id),
        callback_message=callback.message,
    )


@callbacks_router.callback_query(F.data.startswith("ld:"))
async def on_lead_card(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        return
    if not is_staff(callback.from_user.id):
        await callback.answer("Доступ только для сотрудников", show_alert=True)
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        return
    _, short_id, section, page_raw = parts
    try:
        page = max(0, int(page_raw))
    except ValueError:
        page = 0
    reader = get_lead_reader()
    await callback.answer()
    if section == "events":
        event = _approved_events_cache.get(short_id) or reader.get_approved_event_by_short_id(short_id)
        if event is None:
            await callback.answer("Откройте список снова", show_alert=True)
            return
        _approved_events_cache[event.short_id] = event
        await _show_callback_screen(
            callback,
            text=format_approved_event_card(event),
            inline_markup=approved_event_card_keyboard(event.short_id, event.event_url, page),
            reply_markup=main_menu_keyboard(callback.from_user.id),
        )
        return

    lead = _leads_cache.get(short_id) or reader.get_lead_by_short_id(short_id)
    if lead is None:
        await callback.answer("Откройте список заявок снова", show_alert=True)
        return
    _leads_cache[lead.short_id] = lead
    await _show_callback_screen(
        callback,
        text=format_lead_card(lead),
        inline_markup=lead_card_keyboard(lead.short_id, lead.event_url, section, page),
        reply_markup=main_menu_keyboard(callback.from_user.id),
    )


@callbacks_router.callback_query(F.data.startswith("lm:"))
async def on_lead_moderation(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        return
    if not is_staff(callback.from_user.id):
        await callback.answer("Доступ только для сотрудников", show_alert=True)
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 5:
        return
    _, action, short_id, section, page_raw = parts
    try:
        page = max(0, int(page_raw))
    except ValueError:
        page = 0
    reader = get_lead_reader()
    if action == "approve":
        lead = reader.approve_lead(short_id)
        await callback.answer("Заявка одобрена")
        if lead is not None:
            _leads_cache[lead.short_id] = lead
    elif action == "delete":
        lead = reader.delete_lead(short_id)
        await callback.answer("Заявка удалена")
        if lead is not None:
            _leads_cache[lead.short_id] = lead
    else:
        await callback.answer()
        return
    text, markup = _section_payload(reader, section, page)
    await show_user_screen(
        callback.bot,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        text=text,
        inline_markup=markup,
        reply_markup=main_menu_keyboard(callback.from_user.id),
        callback_message=callback.message,
    )


@callbacks_router.callback_query(F.data.startswith("act:"))
async def on_job_actions(callback: CallbackQuery) -> None:
    job_id = (callback.data or "").split(":", 1)[-1]
    job = job_manager.get_job(job_id)
    if job is None or job.result is None:
        await callback.answer("Задание не найдено", show_alert=True)
        return
    await callback.answer()
    if callback.message and callback.from_user:
        from event_search_bot.bot.formatters import format_deep_results_summary

        chunks = format_deep_results_summary(job)
        await _show_callback_screen(
            callback,
            text=chunks[0],
            inline_markup=job_complete_keyboard(job_id),
        )


@callbacks_router.callback_query(F.data.startswith("exp:"))
async def on_export_menu(callback: CallbackQuery) -> None:
    job_id = (callback.data or "").split(":", 1)[-1]
    job = job_manager.get_job(job_id)
    if job is None or job.result is None:
        await callback.answer("Задание не найдено", show_alert=True)
        return
    await callback.answer()
    filters = get_export_filters(job_id)
    if callback.message:
        await _show_callback_screen(
            callback,
            text=format_export_filters_prompt(job),
            inline_markup=export_filters_keyboard(job_id, filters),
        )


@callbacks_router.callback_query(F.data.startswith("efx:"))
async def on_export_filter(callback: CallbackQuery, bot: Bot) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        return
    _, job_id, action = parts
    job = job_manager.get_job(job_id)
    if job is None or job.result is None:
        await callback.answer("Задание не найдено", show_alert=True)
        return

    filters = get_export_filters(job_id)
    if action == "m":
        filters.minsk_only = not filters.minsk_only
        await callback.answer("Фильтр обновлён")
    elif action == "s":
        filters.min_score_50 = not filters.min_score_50
        await callback.answer("Фильтр обновлён")
    elif action == "p":
        filters.partnership_only = not filters.partnership_only
        await callback.answer("Фильтр обновлён")
    elif action in {"csv", "html"}:
        files = report_files(job.result, filters)
        filename, content = files[0 if action == "html" else 1]
        doc = BufferedInputFile(content, filename=filename)
        if callback.from_user and callback.message:
            sent = await bot.send_document(callback.message.chat.id, doc)
            await _track_sent(bot, callback.from_user.id, sent)
        await callback.answer("Файл отправлен")
        return
    else:
        await callback.answer()
        return

    if callback.message:
        await _show_callback_screen(
            callback,
            text=format_export_filters_prompt(job),
            inline_markup=export_filters_keyboard(job_id, filters),
        )


@callbacks_router.callback_query(F.data.startswith("ana:"))
async def on_analytics(callback: CallbackQuery) -> None:
    job_id = (callback.data or "").split(":", 1)[-1]
    job = job_manager.get_job(job_id)
    if job is None or job.result is None:
        await callback.answer("Задание не найдено", show_alert=True)
        return
    await callback.answer()
    filters = get_export_filters(job_id)
    text = build_analytics_text(job.result, filters)
    if callback.message:
        await _show_callback_screen(
            callback,
            text=text,
            inline_markup=job_complete_keyboard(job_id),
        )


@callbacks_router.callback_query(F.data.startswith("shr:"))
async def on_share(callback: CallbackQuery, bot: Bot) -> None:
    job_id = (callback.data or "").split(":", 1)[-1]
    job = job_manager.get_job(job_id)
    if job is None or job.result is None:
        await callback.answer("Задание не найдено", show_alert=True)
        return
    await callback.answer()
    filters = get_export_filters(job_id)
    summary = build_share_summary(job.result, filters)
    chat_id = callback.message.chat.id if callback.message else job.chat_id
    user_id = callback.from_user.id if callback.from_user else job.user_id
    share_text = (
        f"📤 <b>Выжимка для коллеги</b>\n\n{summary}\n\n"
        "<i>Перешлите это сообщение в другой чат.</i>"
    )
    sent_msg = await bot.send_message(
        chat_id,
        share_text,
        disable_web_page_preview=True,
    )
    await _track_sent(bot, user_id, sent_msg)
    files = report_files(job.result, filters)
    html_name, html_content = files[0]
    sent_doc = await bot.send_document(
        chat_id, BufferedInputFile(html_content, filename=html_name)
    )
    await _track_sent(bot, user_id, sent_doc)


@callbacks_router.callback_query(F.data.startswith("evl:"))
async def on_event_list(callback: CallbackQuery) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        return
    job_id = parts[1]
    try:
        page = int(parts[2])
    except ValueError:
        page = 0
    job = job_manager.get_job(job_id)
    events = _job_events(job)
    if job is None or not events:
        await callback.answer("Нет карточек", show_alert=True)
        return
    await callback.answer()
    page_size = 5
    total = len(events)
    max_page = max(0, (total - 1) // page_size)
    page = max(0, min(page, max_page))
    if callback.message:
        await _show_callback_screen(
            callback,
            text=format_event_list_prompt(job, page, page_size),
            inline_markup=event_list_keyboard(job_id, page, total, page_size),
        )


@callbacks_router.callback_query(F.data.startswith("evt:"))
async def on_event_card(callback: CallbackQuery) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        return
    job_id, index_raw = parts[1], parts[2]
    try:
        index = int(index_raw)
    except ValueError:
        return
    job = job_manager.get_job(job_id)
    events = _job_events(job)
    if job is None or not events:
        await callback.answer("Событие не найдено", show_alert=True)
        return
    if index < 0 or index >= len(events):
        await callback.answer("Конец списка", show_alert=True)
        return
    await callback.answer()
    event = events[index]
    if callback.message:
        await _show_callback_screen(
            callback,
            text=format_event_card(event, index, len(events)),
            inline_markup=event_card_keyboard(job_id, event.url, index),
        )
