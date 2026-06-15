from fastapi import APIRouter, Depends, status

from app.application.services.search_query_service import SearchQueryService
from app.presentation.api.dependencies import get_search_query_service
from app.presentation.api.schemas import (
    SearchQueryCreate,
    SearchQueryResponse,
    SearchQueryUpdate,
)

router = APIRouter(prefix="/search-queries", tags=["search-queries"])


@router.get("", response_model=list[SearchQueryResponse])
async def list_search_queries(
    service: SearchQueryService = Depends(get_search_query_service),
) -> list[SearchQueryResponse]:
    queries = await service.list_queries()
    return [SearchQueryResponse.model_validate(q) for q in queries]


@router.post("", response_model=SearchQueryResponse, status_code=status.HTTP_201_CREATED)
async def create_search_query(
    payload: SearchQueryCreate,
    service: SearchQueryService = Depends(get_search_query_service),
) -> SearchQueryResponse:
    entity = await service.create_query(
        query_text=payload.query_text,
        category=payload.category,
        is_active=payload.is_active,
    )
    return SearchQueryResponse.model_validate(entity)


@router.patch("/{query_id}", response_model=SearchQueryResponse)
async def update_search_query(
    query_id: int,
    payload: SearchQueryUpdate,
    service: SearchQueryService = Depends(get_search_query_service),
) -> SearchQueryResponse:
    entity = await service.update_query(
        query_id,
        query_text=payload.query_text,
        category=payload.category,
        is_active=payload.is_active,
    )
    return SearchQueryResponse.model_validate(entity)


@router.delete("/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search_query(
    query_id: int,
    service: SearchQueryService = Depends(get_search_query_service),
) -> None:
    await service.delete_query(query_id)
