from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

logger = logging.getLogger(__name__)

EMPTY_INLINE_MARKUP = InlineKeyboardMarkup(inline_keyboard=[])


@dataclass
class UserScreen:
    chat_id: int
    message_id: int


_screens: dict[int, UserScreen] = {}


async def _delete_message(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest:
        pass


async def _sync_reply_keyboard(
    bot: Bot,
    chat_id: int,
    reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | None,
) -> None:
    if reply_markup is None:
        return
    keyboard_msg = await bot.send_message(chat_id=chat_id, text=".", reply_markup=reply_markup)
    await _delete_message(bot, chat_id, keyboard_msg.message_id)


async def replace_screen(
    bot: Bot,
    *,
    user_id: int,
    chat_id: int,
    text: str,
    reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
    inline_markup: InlineKeyboardMarkup | None = None,
    user_message: Message | None = None,
    disable_web_page_preview: bool = True,
) -> Message:
    """One bot message per user with minimal visual flicker."""
    old = _screens.get(user_id)
    same_as_old = (
        old is not None
        and user_message is not None
        and old.chat_id == user_message.chat.id
        and old.message_id == user_message.message_id
    )
    if user_message is not None and not same_as_old:
        await _delete_message(bot, user_message.chat.id, user_message.message_id)

    sent = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=inline_markup if inline_markup is not None else reply_markup,
        disable_web_page_preview=disable_web_page_preview,
    )
    if inline_markup is not None and reply_markup is not None:
        await _sync_reply_keyboard(bot, chat_id, reply_markup)
    elif inline_markup is None and isinstance(reply_markup, ReplyKeyboardRemove):
        await _sync_reply_keyboard(bot, chat_id, reply_markup)
    if old is not None:
        await _delete_message(bot, old.chat_id, old.message_id)

    _screens[user_id] = UserScreen(chat_id, sent.message_id)
    return sent


async def edit_screen(
    bot: Bot,
    *,
    user_id: int,
    text: str | None = None,
    inline_markup: InlineKeyboardMarkup | None = None,
    clear_inline: bool = False,
    disable_web_page_preview: bool = True,
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


async def edit_screen_markup(
    bot: Bot,
    *,
    user_id: int,
    inline_markup: InlineKeyboardMarkup,
) -> bool:
    screen = _screens.get(user_id)
    if screen is None:
        return False
    try:
        await bot.edit_message_reply_markup(
            chat_id=screen.chat_id,
            message_id=screen.message_id,
            reply_markup=inline_markup,
        )
        return True
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return True
        return False


async def show_user_screen(
    bot: Bot,
    *,
    user_id: int,
    chat_id: int,
    text: str,
    inline_markup: InlineKeyboardMarkup | None = None,
    reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
    callback_message: Message | None = None,
    disable_web_page_preview: bool = True,
) -> None:
    screen = _screens.get(user_id)
    if text and await edit_screen(
        bot,
        user_id=user_id,
        text=text,
        inline_markup=inline_markup,
        disable_web_page_preview=disable_web_page_preview,
    ):
        if callback_message is not None:
            same_as_screen = screen is not None and callback_message.message_id == screen.message_id
            if not same_as_screen:
                await _delete_message(
                    bot, callback_message.chat.id, callback_message.message_id
                )
        if reply_markup is not None:
            await _sync_reply_keyboard(bot, chat_id, reply_markup)
        return

    await replace_screen(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=text,
        inline_markup=inline_markup,
        reply_markup=reply_markup,
        user_message=callback_message,
        disable_web_page_preview=disable_web_page_preview,
    )
