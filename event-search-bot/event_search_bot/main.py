from __future__ import annotations

import asyncio
import contextlib
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from event_search_bot.bot.handlers import get_bot_commands, router
from event_search_bot.config import get_settings
from event_search_bot.pipeline.jobs import job_manager

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )


async def run_bot() -> None:
    settings = get_settings()
    _configure_logging(settings.log_level)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    await bot.set_my_commands(get_bot_commands())

    from event_search_bot.bot.leads_poller import poll_new_leads

    poll_task = asyncio.create_task(poll_new_leads(bot))
    logger.info(
        "Event search bot started (SearXNG: %s, partnership DB: %s)",
        settings.searxng_base_url,
        settings.partnership_data_dir,
    )
    try:
        await dispatcher.start_polling(bot)
    finally:
        poll_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await poll_task
        await job_manager.shutdown()


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
