from app.application.services.enrichment_pipeline import EnrichmentPipelineService
from app.application.services.event_candidate_service import EventCandidateService
from app.application.services.search_provider_service import SearchProviderService
from app.application.services.search_query_service import SearchQueryService
from app.application.services.search_run_service import SearchRunService
from app.application.use_cases.enrich_event import EnrichEventUseCase
from app.application.use_cases.run_search import RunSearchUseCase
from app.application.use_cases.score_event import ScoreEventUseCase
from app.core.config import get_settings
from app.domain.services.deduplication import DeduplicationService
from app.infrastructure.db.repositories import (
    EventCandidateRepository,
    EventReviewRepository,
    SearchQueryRepository,
    SearchRunRepository,
)
from app.infrastructure.enrichment.page_fetcher import HttpPageFetcher
from app.infrastructure.enrichment.supplementary_search import SupplementarySearchService
from sqlalchemy.ext.asyncio import AsyncSession


def create_search_query_service(session: AsyncSession) -> SearchQueryService:
    return SearchQueryService(SearchQueryRepository(session))


def create_search_run_service(session: AsyncSession) -> SearchRunService:
    return SearchRunService(SearchRunRepository(session))


def create_event_candidate_service(session: AsyncSession) -> EventCandidateService:
    return EventCandidateService(
        EventCandidateRepository(session),
        EventReviewRepository(session),
    )


def create_enrich_event_use_case(session: AsyncSession) -> EnrichEventUseCase:
    settings = get_settings()
    provider_service = SearchProviderService(settings)
    supplementary = None
    if settings.supplementary_search_enabled:
        supplementary = SupplementarySearchService(
            provider_service.get_provider(),
            limit=3,
        )
    return EnrichEventUseCase(
        EventCandidateRepository(session),
        HttpPageFetcher(),
        DeduplicationService(),
        supplementary_search=supplementary,
    )


def create_score_event_use_case(session: AsyncSession) -> ScoreEventUseCase:
    return ScoreEventUseCase(EventCandidateRepository(session))


def create_enrichment_pipeline(session: AsyncSession) -> EnrichmentPipelineService:
    return EnrichmentPipelineService(
        create_enrich_event_use_case(session),
        create_score_event_use_case(session),
        EventCandidateRepository(session),
    )


def create_run_search_use_case(session: AsyncSession) -> RunSearchUseCase:
    settings = get_settings()
    provider_service = SearchProviderService(settings)
    return RunSearchUseCase(
        search_query_service=create_search_query_service(session),
        search_run_repository=SearchRunRepository(session),
        event_candidate_repository=EventCandidateRepository(session),
        search_provider=provider_service.get_provider(),
        deduplication_service=DeduplicationService(),
        results_limit=settings.search_results_limit,
        enrichment_pipeline=create_enrichment_pipeline(session) if settings.enrichment_enabled else None,
    )
