import logging

import httpx

from app.application.ports.page_fetcher import FetchedPage
from app.core.exceptions import ValidationError
from app.infrastructure.enrichment.text_sanitize import sanitize_page_text

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; OnlinerEventSearch/1.0; +https://onliner.by)"
)


class HttpPageFetcher:
    def __init__(self, *, timeout: float = 20.0) -> None:
        self._timeout = timeout

    async def fetch(self, url: str) -> FetchedPage:
        if not url.startswith(("http://", "https://")):
            raise ValidationError(message="Invalid event URL", details={"url": url})

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                body = response.content
                if body[:2] == b"PK" or "wordprocessingml" in content_type or "msword" in content_type:
                    raise ValidationError(
                        message="Event URL points to a document, not a web page",
                        details={"url": url, "content_type": content_type},
                    )
                if body and not _looks_like_html(body, content_type):
                    raise ValidationError(
                        message="Event URL does not return HTML content",
                        details={"url": url, "content_type": content_type},
                    )
                html = body.decode(response.encoding or "utf-8", errors="ignore")
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch page %s: %s", url, exc)
            raise ValidationError(
                message="Failed to fetch event page",
                details={"url": url, "reason": str(exc)},
            ) from exc

        text = sanitize_page_text(self._html_to_text(html))
        return FetchedPage(url=url, text=text, html=html)

    def _html_to_text(self, html: str) -> str:
        try:
            import trafilatura

            extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
            if extracted:
                return extracted
        except Exception:
            logger.debug("trafilatura extraction failed, falling back to bs4", exc_info=True)

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text("\n", strip=True)


def _looks_like_html(body: bytes, content_type: str) -> bool:
    if any(token in content_type for token in ("text/html", "application/xhtml", "text/plain")):
        return True
    sample = body[:512].lstrip().lower()
    return sample.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))
