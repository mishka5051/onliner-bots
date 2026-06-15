import uuid

from app.core.exceptions import SearchRunNotFoundError
from app.domain.entities import SearchRunEntity
from app.infrastructure.db.repositories import SearchRunRepository


class SearchRunService:
    def __init__(self, repository: SearchRunRepository) -> None:
        self._repository = repository

    async def get_run(self, run_id: uuid.UUID) -> SearchRunEntity:
        entity = await self._repository.get_by_id(run_id)
        if entity is None:
            raise SearchRunNotFoundError(details={"run_id": str(run_id)})
        return entity

    async def list_runs(self, *, limit: int = 50, offset: int = 0) -> list[SearchRunEntity]:
        return await self._repository.list_all(limit=limit, offset=offset)
