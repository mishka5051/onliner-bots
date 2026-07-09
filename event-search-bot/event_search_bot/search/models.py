from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    title: str
    snippet: str | None
    link: str
    source_domain: str
    relevance_hint: int = 0
