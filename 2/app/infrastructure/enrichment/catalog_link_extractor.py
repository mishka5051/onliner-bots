import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

EVENT_PATH_HINTS = (
    "/event/",
    "/events/",
    "/conference/",
    "/forum/",
    "/expo/",
    "/vystavk",
    "/meropriyat",
    "/konferenc",
    "/festival/",
)

SKIP_PATH_HINTS = (
    "/calendar",
    "/kalendar",
    "/category",
    "/categories",
    "/tag/",
    "/author/",
    "/login",
    "/register",
    "/cart",
    "/search",
    "/page/",
    "#",
    "javascript:",
    "mailto:",
)

DATE_IN_PATH = re.compile(r"20\d{2}|/\d{4}/")


@dataclass(frozen=True)
class ExtractedEventLink:
    title: str
    url: str


class CatalogLinkExtractor:
    def __init__(self, *, max_links: int = 15, min_title_len: int = 8) -> None:
        self._max_links = max_links
        self._min_title_len = min_title_len

    def extract(self, html: str, base_url: str) -> list[ExtractedEventLink]:
        found: dict[str, ExtractedEventLink] = {}

        for link in self._from_json_ld(html, base_url):
            found[link.url] = link

        for link in self._from_anchors(html, base_url):
            if link.url not in found:
                found[link.url] = link

        return list(found.values())[: self._max_links]

    def _from_json_ld(self, html: str, base_url: str) -> list[ExtractedEventLink]:
        links: list[ExtractedEventLink] = []
        for raw in re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            self._collect_json_ld_events(data, base_url, links)
        return links

    def _collect_json_ld_events(self, data: object, base_url: str, links: list[ExtractedEventLink]) -> None:
        if isinstance(data, list):
            for item in data:
                self._collect_json_ld_events(item, base_url, links)
            return
        if not isinstance(data, dict):
            return

        type_value = data.get("@type", "")
        types = type_value if isinstance(type_value, list) else [type_value]
        if any("event" in str(t).lower() for t in types):
            url = data.get("url") or data.get("@id")
            name = data.get("name") or data.get("headline")
            if isinstance(url, str) and isinstance(name, str):
                normalized = self._normalize_url(url, base_url)
                if normalized and len(name.strip()) >= self._min_title_len:
                    links.append(ExtractedEventLink(title=name.strip()[:512], url=normalized))

        for value in data.values():
            if isinstance(value, (dict, list)):
                self._collect_json_ld_events(value, base_url, links)

    def _from_anchors(self, html: str, base_url: str) -> list[ExtractedEventLink]:
        soup = BeautifulSoup(html, "html.parser")
        base_domain = urlparse(base_url).netloc.lower()
        links: list[ExtractedEventLink] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href or any(hint in href.lower() for hint in SKIP_PATH_HINTS):
                continue

            url = self._normalize_url(href, base_url)
            if url is None:
                continue

            parsed = urlparse(url)
            if parsed.netloc.lower() != base_domain:
                continue

            path = parsed.path.lower()
            if not self._looks_like_event_path(path):
                continue

            title = anchor.get_text(" ", strip=True)
            if len(title) < self._min_title_len:
                title = anchor.get("title", "").strip()
            if len(title) < self._min_title_len:
                continue

            links.append(ExtractedEventLink(title=title[:512], url=url))

        return links

    def _looks_like_event_path(self, path: str) -> bool:
        if len(path) < 10:
            return False
        if any(hint in path for hint in SKIP_PATH_HINTS):
            return False
        if any(hint in path for hint in EVENT_PATH_HINTS):
            return True
        if DATE_IN_PATH.search(path) and path.count("/") >= 2:
            return True
        segments = [s for s in path.split("/") if s]
        if not segments:
            return False
        last = segments[-1]
        return len(last) >= 15 and last.count("-") >= 2

    def _normalize_url(self, href: str, base_url: str) -> str | None:
        if href.startswith("//"):
            href = f"{urlparse(base_url).scheme}:{href}"
        if not href.startswith(("http://", "https://")):
            href = urljoin(base_url, href)

        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None

        clean = parsed._replace(fragment="", query="").geturl().rstrip("/")
        if clean.rstrip("/") == base_url.rstrip("/"):
            return None
        return clean
