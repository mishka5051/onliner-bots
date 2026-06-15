import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, status

from app.application.services.search_run_service import SearchRunService
from app.application.use_cases.run_search import RunSearchUseCase
from app.presentation.api.dependencies import get_run_search_use_case, get_search_run_service
from app.presentation.api.schemas import RunSearchResponse, SearchRunResponse

router = APIRouter(prefix="/search-runs", tags=["search-runs"])


@router.post("", response_model=RunSearchResponse, status_code=status.HTTP_201_CREATED)
async def run_all_active_queries(
    use_case: RunSearchUseCase = Depends(get_run_search_use_case),
) -> RunSearchResponse:
    result = await use_case.run_all_active()
    return RunSearchResponse.model_validate(asdict(result))


@router.post("/{query_id}", response_model=RunSearchResponse, status_code=status.HTTP_201_CREATED)
async def run_single_query(
    query_id: int,
    use_case: RunSearchUseCase = Depends(get_run_search_use_case),
) -> RunSearchResponse:
    result = await use_case.run_single(query_id)
    return RunSearchResponse.model_validate(asdict(result))


@router.get("", response_model=list[SearchRunResponse])
async def list_search_runs(
    service: SearchRunService = Depends(get_search_run_service),
) -> list[SearchRunResponse]:
    runs = await service.list_runs()
    return [SearchRunResponse.model_validate(r) for r in runs]


@router.get("/{run_id}", response_model=SearchRunResponse)
async def get_search_run(
    run_id: uuid.UUID,
    service: SearchRunService = Depends(get_search_run_service),
) -> SearchRunResponse:
    run = await service.get_run(run_id)
    return SearchRunResponse.model_validate(run)
