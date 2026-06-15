import logging
import uuid

from app.application.dto.search import RunSearchResultDTO
from app.application.ports.search_provider import SearchProvider
from app.application.services.search_query_service import SearchQueryService
from app.core.exceptions import (
    SearchApiUnavailableError,
    SearchProviderError,
    SearchQueryNotFoundError,
    ValidationError,
)
from app.domain.entities import SearchQueryEntity
from app.domain.enums import SearchRunStatus
from app.domain.services.catalog_page_detector import CatalogPageDetector
from app.domain.services.deduplication import DeduplicationService
from app.application.services.enrichment_pipeline import EnrichmentPipelineService
from app.infrastructure.db.repositories import EventCandidateRepository, SearchRunRepository

logger = logging.getLogger(__name__)


class RunSearchUseCase:
    def __init__(
        self,
        search_query_service: SearchQueryService,
        search_run_repository: SearchRunRepository,
        event_candidate_repository: EventCandidateRepository,
        search_provider: SearchProvider,
        deduplication_service: DeduplicationService,
        *,
        results_limit: int = 10,
        enrichment_pipeline: EnrichmentPipelineService | None = None,
        catalog_detector: CatalogPageDetector | None = None,
    ) -> None:
        self._search_query_service = search_query_service
        self._search_runs = search_run_repository
        self._event_candidates = event_candidate_repository
        self._search_provider = search_provider
        self._deduplication = deduplication_service
        self._results_limit = results_limit
        self._enrichment_pipeline = enrichment_pipeline
        self._catalog_detector = catalog_detector or CatalogPageDetector()

    async def run_all_active(self) -> RunSearchResultDTO:
        queries = await self._search_query_service.list_queries(active_only=True)
        if not queries:
            raise ValidationError(
                message="No active search queries configured",
                details={"field": "search_queries"},
            )
        return await self._execute(queries)

    async def run_single(self, query_id: int) -> RunSearchResultDTO:
        query = await self._search_query_service.get_query(query_id)
        if not query.is_active:
            raise ValidationError(
                message="Search query is disabled",
                details={"query_id": query_id},
            )
        return await self._execute([query])

    async def _execute(self, queries: list[SearchQueryEntity]) -> RunSearchResultDTO:
        run = await self._search_runs.create(status=SearchRunStatus.RUNNING.value)

        total_results = 0
        new_events_count = 0
        duplicate_count = 0
        skipped_catalog_count = 0

        try:
            for query in queries:
                if not query.query_text.strip():
                    raise ValidationError(
                        message="Search query text cannot be empty",
                        details={"query_id": query.id},
                    )

                try:
                    results = await self._search_provider.search(
                        query.query_text,
                        limit=self._results_limit,
                    )
                except SearchProviderError as exc:
                    logger.exception("Search provider failed for query %s", query.id)
                    raise SearchApiUnavailableError(
                        message=str(exc.message),
                        details={"query_id": query.id, **exc.details},
                    ) from exc

                if not results:
                    logger.info("Search API returned empty result for query %s", query.id)
                    continue

                total_results += len(results)

                for result in results:
                    if self._catalog_detector.is_catalog_search_result(
                        url=result.link,
                        title=result.title,
                        snippet=result.snippet,
                    ):
                        skipped_catalog_count += 1
                        continue

                    duplicate_key = self._deduplication.compute_duplicate_key(result.link)
                    existing = await self._event_candidates.get_by_duplicate_key(duplicate_key)
                    if existing is not None:
                        duplicate_count += 1
                        continue

                    await self._event_candidates.create(
                        title=result.title,
                        description=result.snippet,
                        url=result.link,
                        source_domain=result.source_domain,
                        source_query=query.query_text,
                        search_run_id=run.id,
                        duplicate_key=duplicate_key,
                        category=query.category,
                    )
                    new_events_count += 1

            if new_events_count > 0:
                await self._event_candidates.commit()

            if skipped_catalog_count:
                logger.info("Skipped %s catalog/document search results", skipped_catalog_count)

            if self._enrichment_pipeline is not None and new_events_count > 0:
                try:
                    await self._enrichment_pipeline.process_search_run(run.id)
                except Exception:
                    logger.exception("Enrichment pipeline failed for run %s", run.id)

            run.status = SearchRunStatus.COMPLETED.value
            run.total_results = total_results
            run.new_events_count = new_events_count
            run.duplicate_count = duplicate_count
            await self._search_runs.finalize(run)

            return RunSearchResultDTO(
                search_run_id=run.id,
                status=run.status,
                total_results=total_results,
                new_events_count=new_events_count,
                duplicate_count=duplicate_count,
            )
        except (ValidationError, SearchApiUnavailableError, SearchQueryNotFoundError):
            run.status = SearchRunStatus.FAILED.value
            run.error_message = "Search run failed"
            await self._search_runs.finalize(run)
            raise
        except Exception as exc:
            logger.exception("Unexpected error during search run %s", run.id)
            run.status = SearchRunStatus.FAILED.value
            run.error_message = str(exc)
            run.total_results = total_results
            run.new_events_count = new_events_count
            run.duplicate_count = duplicate_count
            await self._search_runs.finalize(run)
            raise SearchApiUnavailableError(
                message="Search run failed unexpectedly",
                details={"run_id": str(run.id), "reason": str(exc)},
            ) from exc
