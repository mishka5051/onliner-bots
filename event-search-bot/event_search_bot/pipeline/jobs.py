from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from event_search_bot.config import Settings, get_settings
from event_search_bot.pipeline.export import build_csv_report, build_html_report
from event_search_bot.pipeline.filters import ExportFilters
from event_search_bot.pipeline.models import PipelineProgress
from event_search_bot.pipeline.runner import DeepSearchResult, DeepSearchRunner

logger = logging.getLogger(__name__)

JobCallback = Callable[["DeepSearchJob"], Awaitable[None] | None]


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DeepSearchJob:
    job_id: str
    user_id: int
    chat_id: int
    query: str
    history_entry_id: int | None = None
    status: JobStatus = JobStatus.QUEUED
    progress: PipelineProgress = field(default_factory=PipelineProgress)
    result: DeepSearchResult | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    _task: asyncio.Task[Any] | None = field(default=None, repr=False)
    _cancel_flag: bool = field(default=False, repr=False)

    def is_active(self) -> bool:
        return self.status in {JobStatus.QUEUED, JobStatus.RUNNING}


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, DeepSearchJob] = {}
        self._user_jobs: dict[int, list[str]] = {}
        self._tasks: set[asyncio.Task[Any]] = set()
        self._execution_slots = asyncio.Semaphore(1)

    def list_user_jobs(self, user_id: int) -> list[DeepSearchJob]:
        ids = self._user_jobs.get(user_id, [])
        return [self._jobs[jid] for jid in ids if jid in self._jobs]

    def get_job(self, job_id: str) -> DeepSearchJob | None:
        return self._jobs.get(job_id)

    def start_job(
        self,
        *,
        user_id: int,
        chat_id: int,
        query: str,
        history_entry_id: int | None = None,
        on_update: JobCallback | None = None,
        on_complete: JobCallback | None = None,
    ) -> DeepSearchJob:
        job_id = str(uuid.uuid4())[:8]
        job = DeepSearchJob(
            job_id=job_id,
            user_id=user_id,
            chat_id=chat_id,
            query=query,
            history_entry_id=history_entry_id,
        )
        self._jobs[job_id] = job
        self._user_jobs.setdefault(user_id, []).append(job_id)

        task = asyncio.create_task(self._run_job(job, on_update=on_update, on_complete=on_complete))
        job._task = task
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        task.add_done_callback(lambda finished: self._log_task_failure(finished, job_id))
        return job

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None or not job.is_active():
            return False
        job._cancel_flag = True
        return True

    async def shutdown(self) -> None:
        for job in self._jobs.values():
            job._cancel_flag = True
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    @staticmethod
    def _log_task_failure(task: asyncio.Task[Any], job_id: str) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("Deep search task %s crashed: %s", job_id, exc, exc_info=exc)

    def _build_runner(self, settings: Settings) -> DeepSearchRunner:
        return DeepSearchRunner(
            searxng_base_url=settings.searxng_base_url,
            search_timeout=settings.search_timeout,
            results_limit=settings.deep_search_results_limit,
            pages_max=settings.deep_search_pages_max,
            query_suffix=settings.query_suffix,
            max_events=settings.deep_enrichment_max_events,
            max_rounds=settings.deep_enrichment_max_rounds,
            batch_size=settings.deep_enrichment_batch_size,
            catalog_budget=settings.deep_catalog_expansion_max,
            catalog_max_links=settings.deep_catalog_max_links,
            fetch_timeout=settings.page_fetch_timeout,
            fetch_concurrency=settings.page_fetch_concurrency,
        )

    async def _run_job(
        self,
        job: DeepSearchJob,
        *,
        on_update: JobCallback | None,
        on_complete: JobCallback | None,
    ) -> None:
        runner: DeepSearchRunner | None = None
        try:
            logger.info("Job %s queued, waiting for execution slot", job.job_id)
            async with self._execution_slots:
                if job._cancel_flag:
                    job.status = JobStatus.CANCELLED
                    return

                job.status = JobStatus.RUNNING
                job.progress.phase = "search"
                if on_update:
                    try:
                        await on_update(job)
                    except Exception:
                        logger.warning(
                            "Job %s initial progress UI update failed",
                            job.job_id,
                            exc_info=True,
                        )

                settings = get_settings()
                runner = self._build_runner(settings)

                async def progress_cb(progress: PipelineProgress) -> None:
                    job.progress = progress
                    if on_update:
                        try:
                            await on_update(job)
                        except Exception:
                            logger.warning(
                                "Job %s progress UI update failed",
                                job.job_id,
                                exc_info=True,
                            )

                result = await runner.run(
                    job.query,
                    on_progress=progress_cb,
                    is_cancelled=lambda: job._cancel_flag,
                )
                job.result = result
                job.progress = result.progress
                job.status = JobStatus.CANCELLED if job._cancel_flag else JobStatus.COMPLETED
                logger.info(
                    "Job %s finished: processed=%s suitable=%s",
                    job.job_id,
                    result.progress.processed,
                    result.progress.suitable_count,
                )
        except Exception as exc:
            logger.exception("Deep search job %s failed", job.job_id)
            job.status = JobStatus.FAILED
            job.error = str(exc)[:500]
        finally:
            job.finished_at = datetime.now(timezone.utc)
            if runner is not None:
                await runner.aclose()
            if on_complete:
                await on_complete(job)


job_manager = JobManager()

_job_export_filters: dict[str, ExportFilters] = {}


def get_export_filters(job_id: str) -> ExportFilters:
    return _job_export_filters.setdefault(job_id, ExportFilters())


def report_files(
    result: DeepSearchResult,
    filters: ExportFilters | None = None,
) -> list[tuple[str, bytes]]:
    safe_query = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in result.query)[:40].strip()
    prefix = safe_query or "search"
    return [
        (f"{prefix}_events.html", build_html_report(result, filters)),
        (f"{prefix}_events.csv", build_csv_report(result, filters)),
    ]
