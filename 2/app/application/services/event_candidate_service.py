import uuid
from datetime import datetime, timezone

from app.application.dto.search import EventFilterDTO
from app.core.exceptions import EventNotFoundError, InvalidEventStatusError
from app.domain.entities import EventCandidateEntity
from app.domain.enums import RelevanceStatus
from app.infrastructure.db.repositories import EventCandidateRepository, EventReviewRepository


class EventCandidateService:
    def __init__(
        self,
        candidate_repository: EventCandidateRepository,
        review_repository: EventReviewRepository,
    ) -> None:
        self._candidates = candidate_repository
        self._reviews = review_repository

    async def get_event(self, event_id: uuid.UUID) -> EventCandidateEntity:
        entity = await self._candidates.get_by_id(event_id)
        if entity is None:
            raise EventNotFoundError(details={"event_id": str(event_id)})
        return entity

    async def list_events(self, filters: EventFilterDTO) -> list[EventCandidateEntity]:
        return await self._candidates.list_filtered(filters)

    async def review_event(
        self,
        event_id: uuid.UUID,
        *,
        status: str,
        comment: str | None = None,
        reviewed_by: str | None = None,
    ) -> EventCandidateEntity:
        try:
            relevance_status = RelevanceStatus(status)
        except ValueError as exc:
            raise InvalidEventStatusError(
                message=f"Invalid event status: {status}",
                details={"status": status, "allowed": [s.value for s in RelevanceStatus]},
            ) from exc

        if relevance_status not in {
            RelevanceStatus.REVIEWED,
            RelevanceStatus.APPROVED,
            RelevanceStatus.REJECTED,
        }:
            raise InvalidEventStatusError(
                message="Review status must be reviewed, approved, or rejected",
                details={"status": status},
            )

        entity = await self.get_event(event_id)
        entity.relevance_status = relevance_status.value
        entity.updated_at = datetime.now(timezone.utc)
        updated = await self._candidates.update(entity)

        await self._reviews.create(
            event_candidate_id=event_id,
            status=relevance_status.value,
            comment=comment,
            reviewed_by=reviewed_by,
        )
        return updated
