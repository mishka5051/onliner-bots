import pytest

from app.application.services.search_query_service import SearchQueryService
from app.application.use_cases.run_search import RunSearchUseCase
from app.domain.services.deduplication import DeduplicationService
from app.infrastructure.db.repositories import (
    EventCandidateRepository,
    SearchQueryRepository,
    SearchRunRepository,
)
from app.infrastructure.search.fake_provider import FakeSearchProvider


@pytest.mark.asyncio
async def test_run_search_use_case_creates_events(db_session):
    use_case = RunSearchUseCase(
        search_query_service=SearchQueryService(SearchQueryRepository(db_session)),
        search_run_repository=SearchRunRepository(db_session),
        event_candidate_repository=EventCandidateRepository(db_session),
        search_provider=FakeSearchProvider(),
        deduplication_service=DeduplicationService(),
        results_limit=5,
    )

    result = await use_case.run_all_active()

    assert result.status == "completed"
    assert result.total_results > 0
    assert result.new_events_count > 0


@pytest.mark.asyncio
async def test_duplicate_result_does_not_create_new_event(db_session):
    from app.infrastructure.db.repositories import SearchQueryRepository

    use_case = RunSearchUseCase(
        search_query_service=SearchQueryService(SearchQueryRepository(db_session)),
        search_run_repository=SearchRunRepository(db_session),
        event_candidate_repository=EventCandidateRepository(db_session),
        search_provider=FakeSearchProvider(),
        deduplication_service=DeduplicationService(),
        results_limit=10,
    )

    first = await use_case.run_all_active()
    second = await use_case.run_all_active()

    assert second.new_events_count == 0
    assert second.duplicate_count >= first.new_events_count
