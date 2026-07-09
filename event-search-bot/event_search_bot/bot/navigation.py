from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup

from event_search_bot.bot.keyboards import EMPTY_INLINE_MARKUP

logger = logging.getLogger(__name__)

_EDIT_MIN_INTERVAL_SEC = 4.0


@dataclass
class UserScreen:
    chat_id: int
    message_id: int


_screens: dict[int, UserScreen] = {}
_extra_messages: dict[int, list[UserScreen]] = {}
_last_edit_at: dict[int, float] = {}
_last_edit_text: dict[int, str] = {}


async def _delete_message(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest:
        pass


async def clear_extra_messages(bot: Bot, user_id: int) -> None:
    for screen in _extra_messages.pop(user_id, []):
        await _delete_message(bot, screen.chat_id, screen.message_id)


async def replace_screen(
    bot: Bot,
    *,
    user_id: int,
    chat_id: int,
    text: str,
    reply_markup: ReplyKeyboardMarkup | None = None,
    inline_markup: InlineKeyboardMarkup | None = None,
    user_message: Message | None = None,
    disable_web_page_preview: bool = True,
) -> Message:
    """One navigation message per user: remove previous screen and the user's tap."""
    await clear_extra_messages(bot, user_id)

    if user_message is not None:
        await _delete_message(bot, user_message.chat.id, user_message.message_id)

    old = _screens.get(user_id)
    if old is not None:
        await _delete_message(bot, old.chat_id, old.message_id)

    sent = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=inline_markup if inline_markup is not None else reply_markup,
        disable_web_page_preview=disable_web_page_preview,
    )
    if inline_markup is not None and reply_markup is not None:
        keyboard_msg = await bot.send_message(chat_id=chat_id, text=".", reply_markup=reply_markup)
        await _delete_message(bot, chat_id, keyboard_msg.message_id)
    _screens[user_id] = UserScreen(chat_id, sent.message_id)
    return sent


async def edit_screen(
    bot: Bot,
    *,
    user_id: int,
    text: str,
    inline_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool = True,
    clear_inline: bool = False,
) -> bool:
    screen = _screens.get(user_id)
    if screen is None:
        return False
    markup = EMPTY_INLINE_MARKUP if clear_inline else inline_markup
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=screen.chat_id,
            message_id=screen.message_id,
            reply_markup=markup,
            disable_web_page_preview=disable_web_page_preview,
        )
        return True
    except TelegramBadRequest as exc:
        lowered = str(exc).lower()
        if "message is not modified" in lowered:
            return True
        if "retry after" in lowered or "too many requests" in lowered:
            logger.warning("Telegram rate limit on edit_screen user=%s: %s", user_id, exc)
            return False
        return False


async def edit_screen_throttled(
    bot: Bot,
    *,
    user_id: int,
    text: str,
    inline_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool = True,
    clear_inline: bool = False,
    force: bool = False,
) -> bool:
    """Update screen at most once every few seconds unless force=True."""
    now = time.monotonic()
    if not force:
        if text == _last_edit_text.get(user_id):
            return True
        if now - _last_edit_at.get(user_id, 0.0) < _EDIT_MIN_INTERVAL_SEC:
            return True
    ok = await edit_screen(
        bot,
        user_id=user_id,
        text=text,
        inline_markup=inline_markup,
        disable_web_page_preview=disable_web_page_preview,
        clear_inline=clear_inline,
    )
    if ok:
        _last_edit_at[user_id] = now
        _last_edit_text[user_id] = text
    return ok


def track_extra_message(user_id: int, chat_id: int, message_id: int) -> None:
    _extra_messages.setdefault(user_id, []).append(UserScreen(chat_id, message_id))


async def show_user_screen(
    bot: Bot,
    *,
    user_id: int,
    chat_id: int,
    text: str,
    inline_markup: InlineKeyboardMarkup | None = None,
    reply_markup: ReplyKeyboardMarkup | None = None,
    callback_message: Message | None = None,
) -> None:
    screen = _screens.get(user_id)
    if await edit_screen(bot, user_id=user_id, text=text, inline_markup=inline_markup):
        if callback_message is not None:
            same_as_screen = screen is not None and callback_message.message_id == screen.message_id
            if not same_as_screen:
                await _delete_message(
                    bot, callback_message.chat.id, callback_message.message_id
                )
        if reply_markup is not None:
            keyboard_msg = await bot.send_message(chat_id=chat_id, text=".", reply_markup=reply_markup)
            await _delete_message(bot, chat_id, keyboard_msg.message_id)
        return
    await replace_screen(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=text,
        inline_markup=inline_markup,
        reply_markup=reply_markup,
        user_message=callback_message,
    )


async def clear_screen(bot: Bot, user_id: int) -> None:
    await clear_extra_messages(bot, user_id)
    screen = _screens.pop(user_id, None)
    if screen is not None:
        await _delete_message(bot, screen.chat_id, screen.message_id)
