import logging
from collections.abc import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class SearchScheduler:
    def __init__(self, cron_expression: str) -> None:
        self._scheduler = AsyncIOScheduler()
        self._cron_expression = cron_expression

    def start(self, job: Callable[[], None]) -> None:
        trigger = CronTrigger.from_crontab(self._cron_expression)

        def _run_job() -> None:
            logger.info("Scheduled search job triggered")
            job()

        self._scheduler.add_job(_run_job, trigger=trigger, id="weekly_search", replace_existing=True)
        self._scheduler.start()
        logger.info("Search scheduler started with cron: %s", self._cron_expression)

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
