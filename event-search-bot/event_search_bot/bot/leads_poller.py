from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from event_search_bot.bot.access import staff_user_ids
from event_search_bot.bot.formatters import format_new_lead_notification
from event_search_bot.config import get_settings
from event_search_bot.partnership.reader import get_lead_reader
from event_search_bot.storage.user_storage import user_storage

logger = logging.getLogger(__name__)


async def poll_new_leads(bot: Bot) -> None:
    settings = get_settings()
    interval = max(30.0, settings.leads_poll_interval_sec)
    meta_key = "last_seen_partnership_lead_id"
    reader = get_lead_reader()

    while True:
        try:
            staff_ids = staff_user_ids()
            recipients = staff_ids or set(user_storage.list_lead_watchers())
            if not recipients or not reader.is_available():
                await asyncio.sleep(interval)
                continue

            leads = reader.list_recent_leads(limit=30)
            if not leads:
                await asyncio.sleep(interval)
                continue

            last_seen = user_storage.get_meta(meta_key)
            if last_seen is None:
                user_storage.set_meta(meta_key, leads[0].id)
                await asyncio.sleep(interval)
                continue

            new_leads = []
            for lead in leads:
                if lead.id == last_seen:
                    break
                new_leads.append(lead)

            if new_leads:
                user_storage.set_meta(meta_key, leads[0].id)
                for lead in reversed(new_leads):
                    text = format_new_lead_notification(lead)
                    for user_id in recipients:
                        try:
                            await bot.send_message(user_id, text, disable_web_page_preview=True)
                        except Exception:
                            logger.warning("Failed to notify user %s about lead %s", user_id, lead.id)
        except Exception:
            logger.exception("Partnership leads polling failed")

        await asyncio.sleep(interval)
