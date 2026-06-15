from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FetchedPage:
    url: str
    text: str
    html: str


class PageFetcherPort(Protocol):
    async def fetch(self, url: str) -> FetchedPage: ...
