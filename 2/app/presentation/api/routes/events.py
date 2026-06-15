import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto.search import EventFilterDTO, build_shortlist_filters
from app.application.services.event_candidate_service import EventCandidateService
from app.application.use_cases.enrich_event import EnrichEventUseCase
from app.application.use_cases.score_event import ScoreEventUseCase
from app.infrastructure.db.session import get_db_session
from app.infrastructure.factory import (
    create_enrich_event_use_case,
    create_score_event_use_case,
)
from app.presentation.api.dependencies import get_event_candidate_service
from app.presentation.api.schemas import EventCandidateResponse, EventReviewRequest

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventCandidateResponse])
async def list_events(
    status: str | None = Query(default=None, alias="status"),
    category: str | None = None,
    source_domain: str | None = None,
    query: str | None = Query(default=None, alias="query"),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    min_score: int | None = Query(default=None, ge=0, le=100),
    is_minsk: bool | None = None,
    is_free: bool | None = None,
    event_type: str | None = None,
    shortlist: bool = False,
    sort_by_score: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: EventCandidateService = Depends(get_event_candidate_service),
) -> list[EventCandidateResponse]:
    if shortlist:
        filters = build_shortlist_filters(limit=limit, offset=offset)
    else:
        filters = EventFilterDTO(
            status=status,
            category=category,
            source_domain=source_domain,
            source_query=query,
            created_from=created_from,
            created_to=created_to,
            min_score=min_score,
            is_minsk=is_minsk,
            is_free=is_free,
            event_type=event_type,
            sort_by_score=sort_by_score,
            limit=limit,
            offset=offset,
        )
    events = await service.list_events(filters)
    return [EventCandidateResponse.model_validate(e) for e in events]


@router.get("/{event_id}", response_model=EventCandidateResponse)
async def get_event(
    event_id: uuid.UUID,
    service: EventCandidateService = Depends(get_event_candidate_service),
) -> EventCandidateResponse:
    event = await service.get_event(event_id)
    return EventCandidateResponse.model_validate(event)


@router.post("/{event_id}/enrich", response_model=EventCandidateResponse)
async def enrich_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    service: EventCandidateService = Depends(get_event_candidate_service),
) -> EventCandidateResponse:
    enrich_use_case = create_enrich_event_use_case(session)
    score_use_case = create_score_event_use_case(session)
    await enrich_use_case.enrich_event(event_id)
    await score_use_case.score_event(event_id)
    event = await service.get_event(event_id)
    return EventCandidateResponse.model_validate(event)


@router.patch("/{event_id}/review", response_model=EventCandidateResponse)
async def review_event(
    event_id: uuid.UUID,
    payload: EventReviewRequest,
    service: EventCandidateService = Depends(get_event_candidate_service),
) -> EventCandidateResponse:
    event = await service.review_event(
        event_id,
        status=payload.status,
        comment=payload.comment,
        reviewed_by=payload.reviewed_by,
    )
    return EventCandidateResponse.model_validate(event)
