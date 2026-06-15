from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.event_candidate_service import EventCandidateService
from app.application.services.search_query_service import SearchQueryService
from app.application.services.search_run_service import SearchRunService
from app.application.use_cases.run_search import RunSearchUseCase
from app.infrastructure.db.session import get_db_session
from app.infrastructure.factory import (
    create_event_candidate_service,
    create_run_search_use_case,
    create_search_query_service,
    create_search_run_service,
)


def get_search_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> SearchQueryService:
    return create_search_query_service(session)


def get_search_run_service(
    session: AsyncSession = Depends(get_db_session),
) -> SearchRunService:
    return create_search_run_service(session)


def get_event_candidate_service(
    session: AsyncSession = Depends(get_db_session),
) -> EventCandidateService:
    return create_event_candidate_service(session)


def get_run_search_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> RunSearchUseCase:
    return create_run_search_use_case(session)
