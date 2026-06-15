import logging
import uuid

from app.application.use_cases.enrich_event import EnrichEventUseCase
from app.application.use_cases.score_event import ScoreEventUseCase
from app.domain.enums import EnrichmentStatus, RelevanceStatus
from app.infrastructure.db.repositories import EventCandidateRepository

logger = logging.getLogger(__name__)


class EnrichmentPipelineService:
    def __init__(
        self,
        enrich_use_case: EnrichEventUseCase,
        score_use_case: ScoreEventUseCase,
        event_repository: EventCandidateRepository,
    ) -> None:
        self._enrich = enrich_use_case
        self._score = score_use_case
        self._events = event_repository

    async def _enrich_and_score(self, event_id: uuid.UUID) -> bool:
        await self._enrich.enrich_event(event_id)
        event = await self._events.get_by_id(event_id)
        if event is None or event.enrichment_status != EnrichmentStatus.COMPLETED.value:
            return False
        if event.relevance_status == RelevanceStatus.REJECTED.value:
            return False

        try:
            await self._score.score_event(event_id)
            await self._events.commit()
        except Exception:
            await self._events.rollback()
            logger.exception("Scoring failed for event %s", event_id)
            return False
        return True

    async def process_search_run(self, search_run_id: uuid.UUID) -> dict[str, int]:
        enriched = 0
        scored = 0
        max_rounds = 5

        for _ in range(max_rounds):
            pending = await self._events.list_by_search_run(
                search_run_id,
                enrichment_status=EnrichmentStatus.PENDING.value,
            )
            if not pending:
                break
            for event in pending:
                if await self._enrich_and_score(event.id):
                    enriched += 1
                    scored += 1

        return {"enriched": enriched, "scored": scored}

    async def process_all_pending(self, *, limit: int = 200) -> dict[str, int]:
        pending = await self._events.list_pending(limit=limit)
        enriched = 0
        scored = 0
        for event in pending:
            if await self._enrich_and_score(event.id):
                enriched += 1
                scored += 1
        return {"enriched": enriched, "scored": scored}
