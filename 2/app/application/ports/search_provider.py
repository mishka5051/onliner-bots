from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    title: str
    snippet: str | None
    link: str
    source_domain: str


class SearchProvider(Protocol):
    async def search(self, query: str, limit: int = 10) -> list[SearchResult]: ...
