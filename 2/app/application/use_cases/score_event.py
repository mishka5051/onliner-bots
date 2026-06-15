import uuid
from datetime import datetime, timezone

from app.core.exceptions import EventNotFoundError
from app.domain.services.event_scoring import EventScoringService
from app.infrastructure.db.repositories import EventCandidateRepository


class ScoreEventUseCase:
    def __init__(
        self,
        event_repository: EventCandidateRepository,
        *,
        scoring_service: EventScoringService | None = None,
    ) -> None:
        self._events = event_repository
        self._scoring = scoring_service or EventScoringService()

    async def score_event(self, event_id: uuid.UUID) -> int:
        event = await self._events.get_by_id(event_id)
        if event is None:
            raise EventNotFoundError(message="Event not found", details={"event_id": str(event_id)})

        result = self._scoring.score(event)
        event.relevance_score = result.relevance_score
        event.score_breakdown = result.score_breakdown
        event.onliner_fit_score = result.onliner_fit_score
        event.updated_at = datetime.now(timezone.utc)
        await self._events.save_scoring(event)
        return result.relevance_score

    async def score_for_run(self, search_run_id: uuid.UUID) -> int:
        events = await self._events.list_by_search_run(search_run_id)
        scored = 0
        for event in events:
            if event.enrichment_status != "completed":
                continue
            await self.score_event(event.id)
            scored += 1
        return scored
