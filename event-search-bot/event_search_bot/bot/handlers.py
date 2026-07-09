from __future__ import annotations

import asyncio
import logging
import re

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, CallbackQuery, Message

from event_search_bot.bot.handlers_callbacks import callbacks_router, open_leads_dashboard, open_leads_section
from event_search_bot.bot.access import is_staff
from event_search_bot.bot.formatters import (
    format_deep_results_summary,
    format_history_list,
    format_job_progress,
    format_results_message,
)
from event_search_bot.bot.keyboards import (
    BTN_APPROVED,
    BTN_BACK,
    BTN_DEEP,
    BTN_HELP,
    BTN_HISTORY,
    BTN_JOBS_LEGACY,
    BTN_LEADS,
    BTN_MENU,
    BTN_QUICK,
    BTN_SEARCH,
    MODE_DEEP,
    MODE_QUICK,
    NAV_BACK,
    TEMPLATE_REPLY_BUTTONS,
    history_keyboard,
    job_complete_keyboard,
    job_view_keyboard,
    main_menu_keyboard,
    mode_search_keyboard,
    search_mode_keyboard,
    search_mode_switch_keyboard,
    sub_screen_keyboard,
)
from event_search_bot.bot.navigation import edit_screen, edit_screen_throttled, replace_screen, show_user_screen
from event_search_bot.config import get_settings
from event_search_bot.pipeline.jobs import JobStatus, job_manager
from event_search_bot.search.service import EventSearchService
from event_search_bot.storage.user_storage import user_storage

logger = logging.getLogger(__name__)

router = Router()
_search_service = EventSearchService()
_user_modes: dict[int, str] = {}
_quick_busy: set[int] = set()
_JOB_ID_RE = re.compile(r"^[a-f0-9]{8}$", re.IGNORECASE)

_MENU_BUTTONS = {
    BTN_SEARCH,
    BTN_QUICK,
    BTN_DEEP,
    BTN_LEADS,
    BTN_APPROVED,
    BTN_HISTORY,
    BTN_HELP,
    BTN_MENU,
    BTN_BACK,
    BTN_JOBS_LEGACY,
    *TEMPLATE_REPLY_BUTTONS.keys(),
}

WELCOME = (
    "👋 <b>Onliner Event Search</b>\n\n"
    "Поиск мероприятий для инфопартнёрств.\n\n"
    "🔍 <b>Поиск</b> — быстрый или глубокий режим на выбор.\n"
    "📥 <b>Заявки</b> — новые из @onliner_partnership_bot.\n"
    "✅ <b>Одобренные</b> — одобренные мероприятия для инфопартнёрств.\n"
    "🕐 <b>История</b> — сохранённые результаты прошлых поисков.\n\n"
    "Выберите раздел 👇"
)

HELP = (
    "<b>Разделы</b>\n\n"
    "🔍 <b>Поиск</b> — выберите быстрый или глубокий режим\n"
    "📥 <b>Заявки</b> — новые заявки на партнёрство\n"
    "✅ <b>Одобренные</b> — одобренные мероприятия\n"
    "🕐 <b>История</b> — последние 10 запросов с результатами\n\n"
    "<b>Команды</b>\n"
    "<code>/search запрос</code> — быстрый поиск\n"
    "<code>/deep запрос</code> — глубокий поиск в фоне\n"
    "Во время глубокого поиска: <code>статус</code>, <code>отмена ID</code>\n\n"
    "<b>Шаблоны</b>: IT Минск, E-commerce, Выставки 2026"
)

MODE_PROMPTS = {
    MODE_QUICK: (
        "🔍 <b>Быстрый поиск</b>\n\n"
        "Напишите запрос или выберите шаблон ниже.\n"
        "Или <code>/search ваш запрос</code>"
    ),
    MODE_DEEP: (
        "🔬 <b>Глубокий поиск</b>\n\n"
        "Опишите тематику или выберите шаблон. Поиск пойдёт <b>в фоне</b>.\n"
        "Или <code>/deep ваш запрос</code>"
    ),
}


def _validate_query(query: str) -> str | None:
    query = query.strip()
    if len(query) < 3:
        return "Запрос слишком короткий. Напишите хотя бы 3 символа."
    if len(query) > 300:
        return "Запрос слишком длинный (макс. 300 символов)."
    return None


def _set_mode(user_id: int, mode: str | None) -> None:
    if mode is None:
        _user_modes.pop(user_id, None)
    else:
        _user_modes[user_id] = mode


async def _show_main_menu(
    bot: Bot,
    *,
    user_id: int,
    chat_id: int,
    user_message: Message | None = None,
) -> None:
    _set_mode(user_id, None)
    await replace_screen(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=WELCOME,
        reply_markup=main_menu_keyboard(user_id),
        user_message=user_message,
    )


async def _show_mode_prompt(
    bot: Bot,
    *,
    user_id: int,
    chat_id: int,
    mode: str,
    user_message: Message | None = None,
) -> None:
    _set_mode(user_id, mode)
    await replace_screen(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=MODE_PROMPTS[mode],
        reply_markup=mode_search_keyboard(user_id),
        inline_markup=search_mode_switch_keyboard(mode),
        user_message=user_message,
    )


async def _safe_edit(message: Message, text: str, **kwargs) -> bool:
    try:
        await message.edit_text(text, **kwargs)
        return True
    except TelegramBadRequest as exc:
        lowered = str(exc).lower()
        if "message is not modified" in lowered:
            return True
        if "message can't be edited" in lowered:
            return False
        raise


async def _show_job_on_screen(
    bot: Bot,
    *,
    user_id: int,
    chat_id: int,
    job,
    user_message: Message | None = None,
) -> None:
    markup = job_view_keyboard(job.job_id) if job.is_active() else None
    await replace_screen(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=format_job_progress(job),
        inline_markup=markup,
        user_message=user_message,
    )


async def _try_handle_job_command(
    bot: Bot, message: Message, text: str, user_id: int
) -> bool:
    lowered = text.lower().strip()
    chat_id = message.chat.id

    if lowered in {"статус", "status"}:
        active = [j for j in job_manager.list_user_jobs(user_id) if j.is_active()]
        if not active:
            await replace_screen(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text="Нет активных заданий.",
                reply_markup=main_menu_keyboard(user_id),
                user_message=message,
            )
            return True
        await _show_job_on_screen(
            bot, user_id=user_id, chat_id=chat_id, job=active[-1], user_message=message
        )
        return True

    if lowered.startswith("отмена ") or lowered.startswith("cancel "):
        job_id = text.split(maxsplit=1)[-1].strip().lower()
        if _JOB_ID_RE.match(job_id):
            if job_manager.cancel_job(job_id):
                await replace_screen(
                    bot,
                    user_id=user_id,
                    chat_id=chat_id,
                    text=f"⏹ Задание <code>{job_id}</code> останавливается…",
                    reply_markup=main_menu_keyboard(user_id),
                    user_message=message,
                )
            else:
                await replace_screen(
                    bot,
                    user_id=user_id,
                    chat_id=chat_id,
                    text="Задание не найдено или уже завершено.",
                    reply_markup=main_menu_keyboard(user_id),
                    user_message=message,
                )
            return True

    if _JOB_ID_RE.match(lowered):
        job = job_manager.get_job(lowered)
        if job is None or job.user_id != user_id:
            await replace_screen(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=f"Задание <code>{lowered}</code> не найдено.",
                reply_markup=main_menu_keyboard(user_id),
                user_message=message,
            )
            return True
        await _show_job_on_screen(
            bot, user_id=user_id, chat_id=chat_id, job=job, user_message=message
        )
        return True

    return False


async def _notify_job_complete(bot: Bot, job) -> None:
    from event_search_bot.bot.keyboards import sub_screen_keyboard

    if job.result is None and job.status != JobStatus.FAILED:
        await replace_screen(
            bot,
            user_id=job.user_id,
            chat_id=job.chat_id,
            text="❌ Глубокий поиск завершился без результата.",
            reply_markup=sub_screen_keyboard(job.user_id),
        )
        return

    if job.status == JobStatus.FAILED:
        await replace_screen(
            bot,
            user_id=job.user_id,
            chat_id=job.chat_id,
            text=(
                f"❌ Глубокий поиск <code>{job.job_id}</code> не удался.\n"
                f"{job.error or 'Неизвестная ошибка'}"
            ),
            reply_markup=sub_screen_keyboard(job.user_id),
        )
        return

    chunks = format_deep_results_summary(job)
    summary_text = "\n\n".join(chunks)
    if job.history_entry_id is not None:
        user_storage.update_history_result(
            job.history_entry_id,
            job_id=job.job_id,
            summary_text=summary_text,
        )

    await replace_screen(
        bot,
        user_id=job.user_id,
        chat_id=job.chat_id,
        text=chunks[0],
        inline_markup=job_complete_keyboard(job.job_id),
        reply_markup=sub_screen_keyboard(job.user_id),
    )


async def _run_quick_search(
    message: Message,
    query: str,
    *,
    user_id: int | None = None,
    chat_id: int | None = None,
) -> None:
    user_id = user_id if user_id is not None else (message.from_user.id if message.from_user else 0)
    chat_id = chat_id if chat_id is not None else message.chat.id
    bot = message.bot

    if user_id in _quick_busy:
        await replace_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text="⏳ Быстрый поиск уже идёт. Подождите пару секунд.",
            reply_markup=sub_screen_keyboard(user_id),
            user_message=message,
        )
        return

    error = _validate_query(query)
    if error:
        await replace_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=error,
            reply_markup=sub_screen_keyboard(user_id),
            user_message=message,
        )
        return

    history_entry_id = user_storage.add_search(user_id, query, MODE_QUICK)

    _quick_busy.add(user_id)
    if not await edit_screen(bot, user_id=user_id, text="🔎 Ищу…"):
        await replace_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text="🔎 Ищу…",
            reply_markup=sub_screen_keyboard(user_id),
            user_message=message,
        )
    else:
        try:
            await message.delete()
        except TelegramBadRequest:
            pass

    try:
        built_query, results = await _search_service.search_events(query)
        chunks = format_results_message(built_query, results)
        summary_text = "\n\n".join(chunks)
        user_storage.update_history_result(history_entry_id, summary_text=summary_text)
        screen_text = chunks[0]
        if len(chunks) > 1:
            screen_text += f"\n\n<i>…ещё {len(chunks) - 1} блок(ов). Полный текст — в истории.</i>"
        await replace_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=screen_text,
            reply_markup=sub_screen_keyboard(user_id),
        )
    except RuntimeError as exc:
        await replace_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=str(exc),
            reply_markup=main_menu_keyboard(user_id),
        )
    except Exception:
        logger.exception("Quick search failed user=%s", user_id)
        await replace_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text="❌ Ошибка поиска. Попробуйте позже.",
            reply_markup=main_menu_keyboard(user_id),
        )
    finally:
        _quick_busy.discard(user_id)
        _set_mode(user_id, None)


async def _start_deep_search(
    message: Message,
    query: str,
    bot: Bot,
    *,
    user_id: int | None = None,
    chat_id: int | None = None,
) -> None:
    user_id = user_id if user_id is not None else (message.from_user.id if message.from_user else 0)
    chat_id = chat_id if chat_id is not None else message.chat.id

    error = _validate_query(query)
    if error:
        await replace_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=error,
            reply_markup=sub_screen_keyboard(user_id),
            user_message=message,
        )
        return

    history_entry_id = user_storage.add_search(user_id, query, MODE_DEEP)

    settings = get_settings()
    active = [j for j in job_manager.list_user_jobs(user_id) if j.is_active()]
    if len(active) >= settings.deep_search_max_active_per_user:
        await replace_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=(
                f"⏳ У вас уже {len(active)} активных глубоких поиска. "
                "Дождитесь завершения или остановите: <code>отмена ID</code> или «статус»."
            ),
            reply_markup=sub_screen_keyboard(user_id),
            user_message=message,
        )
        return

    try:
        async def on_update(active_job) -> None:
            progress = active_job.progress
            force = progress.phase in {"search", "completed"} or progress.processed == 0
            await edit_screen_throttled(
                bot,
                user_id=user_id,
                text=format_job_progress(active_job),
                inline_markup=job_view_keyboard(active_job.job_id),
                force=force,
            )

        async def on_complete(job) -> None:
            await _notify_job_complete(bot, job)

        await replace_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text="🔬 Запускаю глубокий поиск в фоне…",
            reply_markup=sub_screen_keyboard(user_id),
            user_message=message,
        )

        job = job_manager.start_job(
            user_id=user_id,
            chat_id=chat_id,
            query=query,
            history_entry_id=history_entry_id,
            on_update=on_update,
            on_complete=on_complete,
        )

        await asyncio.sleep(0)

        await replace_screen(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=format_job_progress(job),
            inline_markup=job_view_keyboard(job.job_id),
        )
    finally:
        _set_mode(user_id, None)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    await _show_main_menu(
        message.bot,
        user_id=user_id,
        chat_id=message.chat.id,
        user_message=message,
    )


@router.message(Command("help"))
@router.message(F.text == BTN_HELP)
async def cmd_help(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    await replace_screen(
        message.bot,
        user_id=user_id,
        chat_id=message.chat.id,
        text=HELP,
        reply_markup=sub_screen_keyboard(user_id),
        user_message=message,
    )


@router.message(F.text.in_({BTN_MENU, BTN_BACK}))
async def on_main_menu(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    await _show_main_menu(
        message.bot,
        user_id=user_id,
        chat_id=message.chat.id,
        user_message=message,
    )


@router.message(F.text == BTN_SEARCH)
async def on_search_menu(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    _set_mode(user_id, None)
    await replace_screen(
        message.bot,
        user_id=user_id,
        chat_id=message.chat.id,
        text="🔍 <b>Поиск мероприятий</b>\n\nВыберите режим:",
        inline_markup=search_mode_keyboard(),
        reply_markup=sub_screen_keyboard(user_id),
        user_message=message,
    )


async def _open_staff_leads(
    message: Message,
    *,
    section: str,
    unavailable_text: str,
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    if not is_staff(user_id):
        await replace_screen(
            message.bot,
            user_id=user_id,
            chat_id=message.chat.id,
            text="📥 Раздел доступен только сотрудникам Onliner.",
            reply_markup=main_menu_keyboard(user_id),
            user_message=message,
        )
        return
    opened = await open_leads_section(
        message.bot,
        user_id=user_id,
        chat_id=message.chat.id,
        section=section,
        user_message=message,
    )
    if not opened:
        await replace_screen(
            message.bot,
            user_id=user_id,
            chat_id=message.chat.id,
            text=unavailable_text,
            reply_markup=main_menu_keyboard(user_id),
            user_message=message,
        )


@router.message(F.text == BTN_LEADS)
async def on_leads(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    if not is_staff(user_id):
        await replace_screen(
            message.bot,
            user_id=user_id,
            chat_id=message.chat.id,
            text="📥 Раздел доступен только сотрудникам Onliner.",
            reply_markup=main_menu_keyboard(user_id),
            user_message=message,
        )
        return
    opened = await open_leads_dashboard(
        message.bot,
        user_id=user_id,
        chat_id=message.chat.id,
        user_message=message,
    )
    if not opened:
        await replace_screen(
            message.bot,
            user_id=user_id,
            chat_id=message.chat.id,
            text=(
                "📥 База заявок не найдена.\n\n"
                "Убедитесь, что partnership-bot и search-bot используют "
                "общий Docker volume <code>partnership-leads-data</code>."
            ),
            reply_markup=main_menu_keyboard(user_id),
            user_message=message,
        )


@router.message(
    F.text.in_(
        {
            BTN_APPROVED,
            BTN_JOBS_LEGACY,
            "✅ Одобренные мероприятия",
            "✅ Одобренные заявки",
        }
    )
)
async def on_approved(message: Message) -> None:
    await _open_staff_leads(
        message,
        section="events",
        unavailable_text="📥 База одобренных мероприятий недоступна.",
    )


@router.message(F.text == BTN_HISTORY)
async def on_history(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    entries = user_storage.list_history(user_id)
    await replace_screen(
        message.bot,
        user_id=user_id,
        chat_id=message.chat.id,
        text=format_history_list(entries),
        inline_markup=history_keyboard(entries),
        reply_markup=sub_screen_keyboard(user_id),
        user_message=message,
    )


@router.message(Command("search"))
async def cmd_search(message: Message) -> None:
    text = (message.text or "").removeprefix("/search").strip()
    user_id = message.from_user.id if message.from_user else 0
    if not text:
        await _show_mode_prompt(
            message.bot,
            user_id=user_id,
            chat_id=message.chat.id,
            mode=MODE_QUICK,
            user_message=message,
        )
        return
    await _run_quick_search(message, text)


@router.message(Command("deep"))
async def cmd_deep(message: Message, bot: Bot) -> None:
    text = (message.text or "").removeprefix("/deep").strip()
    user_id = message.from_user.id if message.from_user else 0
    if not text:
        await _show_mode_prompt(
            message.bot,
            user_id=user_id,
            chat_id=message.chat.id,
            mode=MODE_DEEP,
            user_message=message,
        )
        return
    await _start_deep_search(message, text, bot)


@router.callback_query(F.data.in_({"mode:quick", "mode:deep"}))
async def on_search_mode_pick(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        return
    mode = MODE_QUICK if callback.data == "mode:quick" else MODE_DEEP
    await callback.answer()
    user_id = callback.from_user.id
    _set_mode(user_id, mode)
    await show_user_screen(
        callback.bot,
        user_id=user_id,
        chat_id=callback.message.chat.id,
        text=MODE_PROMPTS[mode],
        inline_markup=search_mode_switch_keyboard(mode),
        reply_markup=mode_search_keyboard(user_id),
        callback_message=callback.message,
    )


@router.callback_query(F.data == NAV_BACK)
async def on_nav_back(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    _set_mode(callback.from_user.id, None)
    await replace_screen(
        callback.bot,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        text=WELCOME,
        reply_markup=main_menu_keyboard(callback.from_user.id),
        user_message=callback.message,
    )


@router.callback_query(F.data.startswith("cancel:"))
async def on_cancel_job(callback: CallbackQuery) -> None:
    job_id = (callback.data or "").split(":", 1)[-1]
    if job_manager.cancel_job(job_id):
        await callback.answer("Останавливаю…")
        job = job_manager.get_job(job_id)
        if job and callback.from_user:
            await show_user_screen(
                callback.bot,
                user_id=callback.from_user.id,
                chat_id=callback.message.chat.id,
                text=format_job_progress(job),
                inline_markup=job_view_keyboard(job_id),
                callback_message=callback.message,
            )
    else:
        await callback.answer("Задание уже завершено", show_alert=True)


@router.callback_query(F.data.startswith("status:"))
async def on_job_status(callback: CallbackQuery) -> None:
    job_id = (callback.data or "").split(":", 1)[-1]
    job = job_manager.get_job(job_id)
    if job is None:
        await callback.answer("Задание не найдено", show_alert=True)
        return
    await callback.answer()
    if callback.from_user and callback.message:
        markup = job_view_keyboard(job.job_id) if job.is_active() else None
        await show_user_screen(
            callback.bot,
            user_id=callback.from_user.id,
            chat_id=callback.message.chat.id,
            text=format_job_progress(job),
            inline_markup=markup,
            callback_message=callback.message,
        )


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message, bot: Bot) -> None:
    text = (message.text or "").strip()
    user_id = message.from_user.id if message.from_user else 0

    if text in TEMPLATE_REPLY_BUTTONS:
        query = TEMPLATE_REPLY_BUTTONS[text]
        mode = _user_modes.get(user_id, MODE_QUICK)
        if mode == MODE_DEEP:
            await _start_deep_search(message, query, bot)
        else:
            await _run_quick_search(message, query)
        return

    if text in {BTN_MENU, BTN_BACK}:
        await _show_main_menu(
            message.bot,
            user_id=user_id,
            chat_id=message.chat.id,
            user_message=message,
        )
        return

    if text in _MENU_BUTTONS:
        return

    if await _try_handle_job_command(bot, message, text, user_id):
        return

    mode = _user_modes.get(user_id)

    if mode == MODE_DEEP:
        if _JOB_ID_RE.match(text.lower()):
            return
        await _start_deep_search(message, text, bot)
        return

    if mode == MODE_QUICK or mode is None:
        await _run_quick_search(message, text)
        return


def get_bot_commands() -> list[BotCommand]:
    return [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="search", description="Быстрый поиск"),
        BotCommand(command="deep", description="Глубокий поиск (фон)"),
        BotCommand(command="help", description="Справка"),
    ]


router.include_router(callbacks_router)
