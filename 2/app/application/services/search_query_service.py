from app.core.exceptions import SearchQueryInUseError, SearchQueryNotFoundError, ValidationError
from app.domain.entities import SearchQueryEntity
from app.infrastructure.db.repositories import SearchQueryRepository


class SearchQueryService:
    def __init__(self, repository: SearchQueryRepository) -> None:
        self._repository = repository

    async def list_queries(self, *, active_only: bool = False) -> list[SearchQueryEntity]:
        return await self._repository.list_all(active_only=active_only)

    async def get_query(self, query_id: int) -> SearchQueryEntity:
        entity = await self._repository.get_by_id(query_id)
        if entity is None:
            raise SearchQueryNotFoundError(details={"query_id": query_id})
        return entity

    async def create_query(
        self,
        *,
        query_text: str,
        category: str | None = None,
        is_active: bool = True,
    ) -> SearchQueryEntity:
        normalized = query_text.strip()
        if not normalized:
            raise ValidationError(
                message="Search query text cannot be empty",
                details={"field": "query_text"},
            )
        return await self._repository.create(
            query_text=normalized,
            category=category,
            is_active=is_active,
        )

    async def update_query(
        self,
        query_id: int,
        *,
        query_text: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> SearchQueryEntity:
        entity = await self.get_query(query_id)
        if query_text is not None:
            normalized = query_text.strip()
            if not normalized:
                raise ValidationError(
                    message="Search query text cannot be empty",
                    details={"field": "query_text"},
                )
            entity.query_text = normalized
        if category is not None:
            entity.category = category
        if is_active is not None:
            entity.is_active = is_active
        return await self._repository.update(entity)

    async def delete_query(self, query_id: int) -> None:
        entity = await self.get_query(query_id)
        if await self._repository.is_used_in_search_run(entity.query_text):
            raise SearchQueryInUseError(details={"query_id": query_id})
        await self._repository.delete(query_id)
