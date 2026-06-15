import json
import logging
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

NUMERIC_DATE = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b")
ISO_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
RU_DATE = re.compile(
    r"\b(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(20\d{2})\b",
    re.IGNORECASE,
)


def extract_header_text(html: str, *, max_chars: int = 5000) -> str:
    """Text from the top of the page — often contains date, format, and price badges."""
    cutoff_markers = ("похожие мероприятия", "related events", "similar events", "<footer")
    lowered = html.lower()
    end = len(html)
    for marker in cutoff_markers:
        index = lowered.find(marker)
        if index != -1:
            end = min(end, index)
    fragment = html[:end]
    soup = BeautifulSoup(fragment, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)[:max_chars]


def extract_event_date_from_html(html: str) -> datetime | None:
    primary_html = _primary_html_fragment(html)
    for extractor in (
        _from_json_ld,
        _from_time_elements,
        _from_meta_tags,
        _from_text_patterns,
        _from_htmldate,
    ):
        try:
            result = extractor(primary_html)
            if result is not None:
                return result
        except Exception:
            logger.debug("Date extractor %s failed", extractor.__name__, exc_info=True)
    return None


def _primary_html_fragment(html: str) -> str:
    lowered = html.lower()
    for marker in ("похожие мероприятия", "related events", "similar events"):
        index = lowered.find(marker)
        if index != -1:
            return html[:index]
    return html


def _parse_date_parts(year: int, month: int, day: int) -> datetime | None:
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _from_json_ld(html: str) -> datetime | None:
    for match in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.S | re.I,
    ):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        for node in _walk_json(payload):
            if not isinstance(node, dict):
                continue
            types = node.get("@type")
            if isinstance(types, str):
                types = [types]
            if not types or not any("event" in t.lower() for t in types):
                continue
            for key in ("startDate", "startTime", "datePublished"):
                parsed = _parse_iso_datetime(node.get(key))
                if parsed is not None:
                    return parsed
    return None


def _walk_json(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_json(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_json(item)


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if "T" in value:
        value = value.split("T", 1)[0]
    match = ISO_DATE.search(value)
    if not match:
        return None
    return _parse_date_parts(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _from_time_elements(html: str) -> datetime | None:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.find_all("time"):
        for attr in ("datetime", "content"):
            parsed = _parse_iso_datetime(element.get(attr))
            if parsed is not None:
                return parsed
    return None


def _from_meta_tags(html: str) -> datetime | None:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.find_all("meta"):
        key = (element.get("property") or element.get("name") or "").lower()
        if "date" not in key and "time" not in key:
            continue
        parsed = _parse_iso_datetime(element.get("content"))
        if parsed is not None:
            return parsed
    return None


def _from_text_patterns(html: str) -> datetime | None:
    text = extract_header_text(html, max_chars=8000)
    for pattern in (NUMERIC_DATE, ISO_DATE, RU_DATE):
        match = pattern.search(text)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 3 and groups[0].startswith("20"):
            parsed = _parse_date_parts(int(groups[0]), int(groups[1]), int(groups[2]))
        elif len(groups) == 3 and groups[1].lower() in RU_MONTHS:
            parsed = _parse_date_parts(int(groups[2]), RU_MONTHS[groups[1].lower()], int(groups[0]))
        else:
            parsed = _parse_date_parts(int(groups[2]), int(groups[1]), int(groups[0]))
        if parsed is not None:
            return parsed
    return None


def _from_htmldate(html: str) -> datetime | None:
    try:
        from htmldate import find_date
    except ImportError:
        return None
    found = find_date(html, original_date=True)
    if not found:
        return None
    try:
        return datetime.fromisoformat(found[:10])
    except ValueError:
        return None
