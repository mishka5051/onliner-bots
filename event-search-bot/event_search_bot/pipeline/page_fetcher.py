from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from event_search_bot.pipeline.catalog import PreFetchFilter
from event_search_bot.pipeline.text_sanitize import sanitize_page_text

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class FetchedPage:
    url: str
    text: str
    html: str


class FetchSkipped(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class PageFetchCache:
    def __init__(self, *, ttl_seconds: int = 3600) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, FetchedPage]] = {}

    def get(self, url: str) -> FetchedPage | None:
        entry = self._store.get(url)
        if entry is None:
            return None
        expires_at, page = entry
        if time.monotonic() > expires_at:
            del self._store[url]
            return None
        return page

    def set(self, url: str, page: FetchedPage) -> None:
        self._store[url] = (time.monotonic() + self._ttl, page)


class HttpPageFetcher:
    _client: httpx.AsyncClient | None = None

    def __init__(
        self,
        *,
        timeout: float = 25.0,
        cache: PageFetchCache | None = None,
        pre_fetch_filter: PreFetchFilter | None = None,
    ) -> None:
        self._timeout = timeout
        self._cache = cache or PageFetchCache()
        self._pre_fetch = pre_fetch_filter or PreFetchFilter()

    async def aclose(self) -> None:
        if HttpPageFetcher._client is not None:
            await HttpPageFetcher._client.aclose()
            HttpPageFetcher._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if HttpPageFetcher._client is None:
            HttpPageFetcher._client = httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return HttpPageFetcher._client

    async def fetch(self, url: str, *, title: str = "", snippet: str | None = None) -> FetchedPage:
        skip_reason = self._pre_fetch.should_skip(url=url, title=title, snippet=snippet)
        if skip_reason:
            raise FetchSkipped(skip_reason)

        cached = self._cache.get(url)
        if cached is not None:
            return cached

        if not url.startswith(("http://", "https://")):
            raise FetchSkipped("Некорректный URL")

        try:
            client = self._get_client()
            response = await client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            body = response.content
            if body[:2] == b"PK" or "wordprocessingml" in content_type or "msword" in content_type:
                raise FetchSkipped("Документ, не веб-страница")
            if body and not _looks_like_html(body, content_type):
                raise FetchSkipped("Ответ не является HTML")
            html = body.decode(response.encoding or "utf-8", errors="ignore")
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch page %s: %s", url, exc)
            raise FetchSkipped(f"Ошибка загрузки: {exc}") from exc

        text = sanitize_page_text(self._html_to_text(html))
        page = FetchedPage(url=url, text=text, html=html)
        self._cache.set(url, page)
        return page

    def _html_to_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text("\n", strip=True)


def _looks_like_html(body: bytes, content_type: str) -> bool:
    if any(token in content_type for token in ("text/html", "application/xhtml", "text/plain")):
        return True
    sample = body[:512].lstrip().lower()
    return sample.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))
