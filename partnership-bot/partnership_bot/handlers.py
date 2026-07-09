"""Telegram-бот: пошаговый сбор заявок на инфопартнёрство (Onlíner)."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, User
from aiogram.utils.keyboard import InlineKeyboardBuilder

from partnership_bot.navigation import edit_screen_markup, replace_screen, show_user_screen
from partnership_bot.storage import storage

logger = logging.getLogger(__name__)

router = Router()

TOTAL_STEPS = 9

STEP_TITLE = "title"
STEP_DATE = "date"
STEP_CITY = "city"
STEP_CITY_CUSTOM = "city_custom"
STEP_URL = "url"
STEP_FORMAT = "format"
STEP_AUDIENCE = "audience"
STEP_PARTNERSHIP = "partnership"
STEP_CONTACT = "contact"
STEP_COMMENT = "comment"
STEP_CONFIRM = "confirm"

SKIP = "⏭ Пропустить"
CANCEL = "❌ Отмена"
BACK = "◀️ Назад"

STEP_SEQUENCE = [
    STEP_TITLE,
    STEP_DATE,
    STEP_CITY,
    STEP_URL,
    STEP_FORMAT,
    STEP_AUDIENCE,
    STEP_PARTNERSHIP,
    STEP_CONTACT,
    STEP_COMMENT,
    STEP_CONFIRM,
]

FORMAT_OPTIONS = [
    ("conference", "🎤 Конференция"),
    ("festival", "🎪 Фестиваль"),
    ("exhibition", "🖼 Выставка"),
    ("meetup", "💬 Митап"),
    ("urban", "🏙 Городское"),
    ("other", "📦 Другое"),
]

AUDIENCE_OPTIONS = [
    ("до 500", "👤 До 500"),
    ("500-2000", "👥 500–2000"),
    ("2000+", "🏟 2000+"),
]

PARTNERSHIP_OPTIONS = [
    ("info", "📰 Инфопартнёр"),
    ("media", "📺 Медиапартнёр"),
    ("announce", "📢 Анонсы"),
    ("other", "✨ Другое"),
]

CITY_OPTIONS = [
    ("Минск", "Минск"),
    ("Гродно", "Гродно"),
    ("Брест", "Брест"),
    ("Гомель", "Гомель"),
    ("Vitebsk", "Витебск"),
    ("other", "📍 Другой город"),
]

PARTNERSHIP_LABELS = dict(PARTNERSHIP_OPTIONS)
FORMAT_LABELS = dict(FORMAT_OPTIONS)


def bot_commands() -> list[BotCommand]:
    return [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="apply", description="Подать заявку"),
        BotCommand(command="status", description="Текущая заявка"),
        BotCommand(command="cancel", description="Отменить заявку"),
        BotCommand(command="help", description="Справка"),
    ]


def _step_number(step: str) -> int:
    try:
        idx = STEP_SEQUENCE.index(step)
        return min(idx + 1, TOTAL_STEPS)
    except ValueError:
        return 1


def _progress_bar(step: str) -> str:
    n = _step_number(step)
    filled = "▰" * n
    empty = "▱" * (TOTAL_STEPS - n)
    return f"{filled}{empty}  {n}/{TOTAL_STEPS}"


def _step_message(step: str, title: str, hint: str) -> str:
    return f"<b>{title}</b>\n<i>{_progress_bar(step)}</i>\n\n{hint}"


def _nav_keyboard(*, skip: bool = False, back: bool = True) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    if back:
        rows.append([KeyboardButton(text=BACK)])
    if skip:
        rows.append([KeyboardButton(text=SKIP)])
    rows.append([KeyboardButton(text=CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def _cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL)]],
        resize_keyboard=True,
    )


def _main_menu_inline() -> Any:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Подать заявку", callback_data="menu:apply")
    builder.button(text="ℹ️ Как это работает", callback_data="menu:about")
    builder.adjust(1)
    return builder.as_markup()


def _format_inline() -> Any:
    builder = InlineKeyboardBuilder()
    for key, label in FORMAT_OPTIONS:
        builder.button(text=label, callback_data=f"fmt:{key}")
    builder.adjust(2)
    return builder.as_markup()


def _audience_inline() -> Any:
    builder = InlineKeyboardBuilder()
    for key, label in AUDIENCE_OPTIONS:
        builder.button(text=label, callback_data=f"aud:{key}")
    builder.adjust(1)
    return builder.as_markup()


def _city_inline() -> Any:
    builder = InlineKeyboardBuilder()
    for key, label in CITY_OPTIONS:
        builder.button(text=label, callback_data=f"city:{key}")
    builder.adjust(2)
    return builder.as_markup()


def _partnership_inline(selected: list[str]) -> Any:
    builder = InlineKeyboardBuilder()
    for key, label in PARTNERSHIP_OPTIONS:
        mark = "✅ " if key in selected else ""
        builder.button(text=f"{mark}{label}", callback_data=f"prt:{key}")
    builder.button(text="➡️ Далее", callback_data="prt:done")
    builder.adjust(2)
    return builder.as_markup()


def _confirm_inline() -> Any:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить заявку", callback_data="cfm:ok")
    builder.button(text="✏️ Заполнить заново", callback_data="cfm:restart")
    builder.button(text="◀️ Изменить контакт", callback_data="cfm:edit_contact")
    builder.adjust(1)
    return builder.as_markup()


def _after_submit_inline() -> Any:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Подать ещё заявку", callback_data="menu:apply")
    builder.adjust(1)
    return builder.as_markup()


def _parse_date(text: str) -> datetime | None:
    text = text.strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _partnership_labels(keys: list[str]) -> str:
    return ", ".join(PARTNERSHIP_LABELS.get(k, k) for k in keys) or "—"


def _preview_html(draft: dict[str, Any]) -> str:
    return (
        "📋 <b>Проверьте заявку</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{draft.get('event_title', '—')}</b>\n"
        f"📅 {draft.get('event_date_display', 'не указана')}\n"
        f"📍 {draft.get('city', '—')}\n"
        f"🔗 {draft.get('event_url') or '—'}\n"
        f"🎯 {draft.get('event_format_label', draft.get('event_format', '—'))}\n"
        f"👥 {draft.get('audience_range', '—')}\n"
        f"🤝 {_partnership_labels(draft.get('partnership_types') or [])}\n"
        f"📞 {draft.get('contact', '—')}\n"
        f"💬 {draft.get('comment') or '—'}"
    )


def _status_preview(step: str, draft: dict[str, Any]) -> str:
    lines = [f"<b>Черновик заявки</b>\n<i>{_progress_bar(step)}</i>\n"]
    if draft.get("event_title"):
        lines.append(f"📌 {draft['event_title']}")
    if draft.get("event_date_display"):
        lines.append(f"📅 {draft['event_date_display']}")
    if draft.get("city"):
        lines.append(f"📍 {draft['city']}")
    if draft.get("event_url"):
        lines.append(f"🔗 {draft['event_url']}")
    if draft.get("event_format_label"):
        lines.append(f"🎯 {draft['event_format_label']}")
    if draft.get("audience_range"):
        lines.append(f"👥 {draft['audience_range']}")
    if draft.get("partnership_types"):
        lines.append(f"🤝 {_partnership_labels(draft['partnership_types'])}")
    if draft.get("contact"):
        lines.append(f"📞 {draft['contact']}")
    if not draft.get("event_title"):
        lines.append("\nПока пусто. Нажмите /apply")
    return "\n".join(lines)


async def _screen_message(
    message: Message,
    text: str,
    *,
    reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
    inline_markup: Any = None,
) -> None:
    await replace_screen(
        message.bot,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        text=text,
        reply_markup=reply_markup,
        inline_markup=inline_markup,
        user_message=message,
    )


async def _screen_callback(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
    inline_markup: Any = None,
) -> None:
    if not callback.from_user or not callback.message:
        return
    await show_user_screen(
        callback.bot,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=reply_markup,
        inline_markup=inline_markup,
        callback_message=callback.message,
    )


async def _begin_apply(message: Message, user: User, *, drop_message: Message | None = None) -> None:
    draft: dict[str, Any] = {"telegram_username": user.username, "partnership_types": []}
    storage.save_session(user.id, step=STEP_TITLE, draft=draft)
    await replace_screen(
        message.bot,
        user_id=user.id,
        chat_id=message.chat.id,
        text=_step_message(
            STEP_TITLE,
            "Название мероприятия",
            "Как называется событие?\n\n"
            "<i>Пример: Belarus IT Forum 2026, Минский марафон, Startup Day</i>",
        ),
        reply_markup=_cancel_keyboard(),
        user_message=drop_message,
    )


async def _notify_staff(bot: Bot, lead) -> None:
    from partnership_bot.config import staff_notify_ids

    ids = staff_notify_ids()
    if not ids:
        return
    text = (
        "🆕 <b>Новая заявка на инфопартнёрство</b>\n"
        f"<b>{lead.event_title}</b>\n"
        f"Город: {lead.city or '—'}\n"
        f"ID: <code>{lead.short_id}</code>"
    )
    for user_id in ids:
        try:
            await bot.send_message(user_id, text, parse_mode="HTML")
        except Exception:
            logger.warning("Failed to notify staff user %s", user_id)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    storage.clear_session(message.from_user.id)
    await replace_screen(
        message.bot,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        text=(
            "👋 <b>Onlíner · заявки на инфопартнёрство</b>\n\n"
            "Поможем передать предложение команде маркетинга: "
            "название, дату, формат и контакт — за пару минут.\n\n"
            "Выберите действие 👇"
        ),
        inline_markup=_main_menu_inline(),
        reply_markup=ReplyKeyboardRemove(),
        user_message=message,
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await _screen_message(
        message,
        "<b>Как подать заявку</b>\n\n"
        "1️⃣ /apply — пошаговая форма (≈2 мин)\n"
        "2️⃣ Укажите ссылку на сайт мероприятия (если есть)\n"
        "3️⃣ Маркетинг Onlíner свяжется с вами\n\n"
        "/status — посмотреть черновик\n"
        "/cancel — отменить текущую заявку",
        inline_markup=_main_menu_inline(),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    session = storage.get_session(message.from_user.id)
    if session is None:
        await _screen_message(
            message,
            "Нет активной заявки. Нажмите /apply или кнопку ниже.",
            inline_markup=_main_menu_inline(),
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    step, draft = session
    await _screen_message(message, _status_preview(step, draft), reply_markup=_cancel_keyboard())


@router.message(Command("cancel"))
@router.message(F.text == CANCEL)
async def cmd_cancel(message: Message) -> None:
    storage.clear_session(message.from_user.id)
    await replace_screen(
        message.bot,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        text="Заявка отменена. Если передумаете — /apply",
        inline_markup=_main_menu_inline(),
        reply_markup=ReplyKeyboardRemove(),
        user_message=message,
    )


@router.message(Command("apply"))
async def cmd_apply(message: Message) -> None:
    await _begin_apply(message, message.from_user, drop_message=message)


@router.callback_query(F.data.startswith("menu:"))
async def on_menu(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        await callback.answer()
        return
    action = (callback.data or "").split(":")[1]
    if action == "apply":
        await callback.answer()
        await _begin_apply(callback.message, callback.from_user, drop_message=callback.message)
    elif action == "about":
        await callback.answer()
        await _screen_callback(
            callback,
            "<b>Onlíner и инфопартнёрство</b>\n\n"
            "Мы ищем масштабные события в Минске и Беларуси: "
            "конференции, фестивали, выставки, митапы.\n\n"
            "Инфопартнёрство — это анонсы, медиаподдержка и охват аудитории Onlíner.\n\n"
            "Заявка занимает 2–3 минуты. Можно пропускать необязательные поля.",
            inline_markup=_main_menu_inline(),
        )
    else:
        await callback.answer()


@router.message(F.text == BACK)
async def on_back(message: Message) -> None:
    user_id = message.from_user.id
    session = storage.get_session(user_id)
    if session is None:
        return
    step, draft = session
    if step == STEP_TITLE:
        await cmd_cancel(message)
        return
    try:
        idx = STEP_SEQUENCE.index(step)
        prev = STEP_SEQUENCE[max(0, idx - 1)]
    except ValueError:
        prev = STEP_TITLE
    storage.save_session(user_id, step=prev, draft=draft)
    await _screen_message(
        message,
        "Шаг назад. Продолжите с предыдущего поля или /cancel.",
        reply_markup=_nav_keyboard(skip=True),
    )


@router.message(F.text)
async def on_text(message: Message) -> None:
    user_id = message.from_user.id
    session = storage.get_session(user_id)
    if session is None:
        if message.text and message.text.startswith("/"):
            return
        await _screen_message(
            message,
            "Нажмите /apply или выберите в меню:",
            inline_markup=_main_menu_inline(),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    step, draft = session
    text = (message.text or "").strip()

    if text == CANCEL:
        await cmd_cancel(message)
        return
    if text == BACK:
        await on_back(message)
        return

    if step == STEP_TITLE:
        if len(text) < 3:
            await _screen_message(message, "Слишком коротко. Введите полное название мероприятия:", reply_markup=_cancel_keyboard())
            return
        draft["event_title"] = text
        storage.save_session(user_id, step=STEP_DATE, draft=draft)
        await _screen_message(
            message,
            _step_message(STEP_DATE, "Дата мероприятия", "Формат: <code>15.09.2026</code> или «Пропустить»"),
            reply_markup=_nav_keyboard(skip=True),
        )
        return

    if step == STEP_DATE:
        if text == SKIP:
            draft["event_date_display"] = "не указана"
        else:
            parsed = _parse_date(text)
            if parsed is None:
                await _screen_message(
                    message,
                    "Не распознал дату. Пример: <code>15.09.2026</code>",
                    reply_markup=_nav_keyboard(skip=True),
                )
                return
            draft["event_date"] = parsed.isoformat()
            draft["event_date_display"] = parsed.strftime("%d.%m.%Y")
        storage.save_session(user_id, step=STEP_CITY, draft=draft)
        await _screen_message(
            message,
            _step_message(STEP_CITY, "Город", "Выберите город кнопкой или введите название:"),
            reply_markup=_cancel_keyboard(),
            inline_markup=_city_inline(),
        )
        return

    if step in (STEP_CITY_CUSTOM, STEP_CITY):
        if len(text) < 2:
            await _screen_message(message, "Укажите город:", reply_markup=_cancel_keyboard())
            return
        draft["city"] = text
        storage.save_session(user_id, step=STEP_URL, draft=draft)
        await _screen_message(
            message,
            _step_message(
                STEP_URL,
                "Ссылка на сайт / афишу",
                "Ссылка помогает автоматически оценить событие.\n\n<i>Пример: https://event.by/...</i>",
            ),
            reply_markup=_nav_keyboard(skip=True),
        )
        return

    if step == STEP_URL:
        if text != SKIP:
            if not re.match(r"^https?://", text, re.I):
                await _screen_message(
                    message,
                    "Нужна ссылка вида <code>https://...</code> или «Пропустить»",
                    reply_markup=_nav_keyboard(skip=True),
                )
                return
            draft["event_url"] = text
        storage.save_session(user_id, step=STEP_FORMAT, draft=draft)
        await _screen_message(
            message,
            _step_message(STEP_FORMAT, "Формат мероприятия", "Выберите тип события:"),
            reply_markup=ReplyKeyboardRemove(),
            inline_markup=_format_inline(),
        )
        return

    if step == STEP_CONTACT:
        if len(text) < 5:
            await _screen_message(message, "Укажите email, телефон или @username Telegram:", reply_markup=_cancel_keyboard())
            return
        draft["contact"] = text
        draft.pop("contact_name", None)
        draft.pop("contact_email", None)
        draft.pop("contact_phone", None)
        if "@" in text and "." in text and not text.startswith("@"):
            draft["contact_email"] = text
        elif text.startswith("@"):
            draft["contact_phone"] = text
        elif any(ch.isdigit() for ch in text):
            draft["contact_phone"] = text
        else:
            draft["contact_name"] = text
        storage.save_session(user_id, step=STEP_COMMENT, draft=draft)
        await _screen_message(
            message,
            _step_message(
                STEP_COMMENT,
                "Комментарий",
                "Расскажите, чего ждёте от партнёрства с Onlíner (или «Пропустить»)",
            ),
            reply_markup=_nav_keyboard(skip=True),
        )
        return

    if step == STEP_COMMENT:
        if text != SKIP:
            draft["comment"] = text
        storage.save_session(user_id, step=STEP_CONFIRM, draft=draft)
        await _screen_message(
            message,
            _preview_html(draft),
            reply_markup=ReplyKeyboardRemove(),
            inline_markup=_confirm_inline(),
        )
        return


@router.callback_query(F.data.regexp(r"^(city|fmt|aud|prt|cfm):"))
async def on_form_callback(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not callback.message:
        await callback.answer()
        return

    user_id = callback.from_user.id
    session = storage.get_session(user_id)
    if session is None:
        await callback.answer("Сессия истекла. Нажмите /apply", show_alert=True)
        return

    step, draft = session
    parts = (callback.data or "").split(":", 1)
    if len(parts) != 2:
        await callback.answer()
        return
    kind, action = parts[0], parts[1]

    if kind == "cfm" and action == "restart":
        storage.clear_session(user_id)
        await callback.answer()
        await _screen_callback(
            callback,
            "Начните заново: /apply",
            inline_markup=_main_menu_inline(),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if kind == "cfm" and action == "edit_contact":
        storage.save_session(user_id, step=STEP_CONTACT, draft=draft)
        await callback.answer()
        await _screen_callback(
            callback,
            _step_message(STEP_CONTACT, "Контакт", "Email, телефон или @username:"),
            reply_markup=_cancel_keyboard(),
        )
        return

    if kind == "city" and step in (STEP_CITY, STEP_CITY_CUSTOM):
        if action == "other":
            storage.save_session(user_id, step=STEP_CITY_CUSTOM, draft=draft)
            await callback.answer()
            await _screen_callback(
                callback,
                "Введите название города:",
                reply_markup=_cancel_keyboard(),
            )
        else:
            draft["city"] = action
            storage.save_session(user_id, step=STEP_URL, draft=draft)
            await callback.answer()
            await _screen_callback(
                callback,
                _step_message(STEP_URL, "Ссылка", "Ссылка на сайт или «Пропустить» на клавиатуре"),
                reply_markup=_nav_keyboard(skip=True),
            )
        return

    if kind == "fmt" and step == STEP_FORMAT:
        draft["event_format"] = action
        draft["event_format_label"] = FORMAT_LABELS.get(action, action)
        storage.save_session(user_id, step=STEP_AUDIENCE, draft=draft)
        await callback.answer()
        await _screen_callback(
            callback,
            _step_message(STEP_AUDIENCE, "Аудитория", "Сколько человек ожидаете?"),
            inline_markup=_audience_inline(),
        )
        return

    if kind == "aud" and step == STEP_AUDIENCE:
        draft["audience_range"] = action
        draft.setdefault("partnership_types", [])
        storage.save_session(user_id, step=STEP_PARTNERSHIP, draft=draft)
        await callback.answer()
        await _screen_callback(
            callback,
            _step_message(
                STEP_PARTNERSHIP,
                "Формат партнёрства",
                "Можно выбрать несколько вариантов, затем «Далее»",
            ),
            inline_markup=_partnership_inline(draft["partnership_types"]),
        )
        return

    if kind == "prt" and step == STEP_PARTNERSHIP:
        if action == "done":
            if not draft.get("partnership_types"):
                await callback.answer("Выберите хотя бы один вариант", show_alert=True)
                return
            storage.save_session(user_id, step=STEP_CONTACT, draft=draft)
            await callback.answer()
            await _screen_callback(
                callback,
                _step_message(STEP_CONTACT, "Контакт", "Как с вами связаться?"),
                reply_markup=_cancel_keyboard(),
            )
            return
        selected: list[str] = draft.setdefault("partnership_types", [])
        if action in selected:
            selected.remove(action)
        else:
            selected.append(action)
        storage.save_session(user_id, step=STEP_PARTNERSHIP, draft=draft)
        await edit_screen_markup(
            callback.bot,
            user_id=user_id,
            inline_markup=_partnership_inline(selected),
        )
        await callback.answer()
        return

    if kind == "cfm" and action == "ok" and step == STEP_CONFIRM:
        await _screen_callback(callback, "⏳ Отправляю заявку…")
        try:
            lead = storage.create_lead(
                draft,
                telegram_user_id=user_id,
                username=callback.from_user.username,
            )
        except Exception:
            logger.exception("Failed to submit lead user=%s", user_id)
            await _screen_callback(
                callback,
                "❌ Не удалось сохранить заявку. Попробуйте ещё раз или напишите на marketing@onliner.by",
                inline_markup=_confirm_inline(),
            )
            await callback.answer("Ошибка", show_alert=True)
            return

        storage.clear_session(user_id)
        await _notify_staff(bot, lead)
        await _screen_callback(
            callback,
            f"✅ <b>Заявка принята!</b>\n"
            f"Номер: <code>{lead.short_id}</code>\n\n"
            "Команда маркетинга Onlíner рассмотрит предложение и свяжется с вами.\n\n"
            "Что дальше?",
            inline_markup=_after_submit_inline(),
            reply_markup=ReplyKeyboardRemove(),
        )
        await callback.answer("Отправлено ✅")
        return

    await callback.answer()


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp
