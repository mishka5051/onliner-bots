from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape

_SCRIPT_JSON_LD = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class StructuredEventData:
    name: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    city: str | None = None
    country: str | None = None
    is_free: bool | None = None
    description: str | None = None
    organizer: str | None = None
    event_type_hint: str | None = None
    source: str = "json-ld"


class StructuredEventExtractor:
    def extract_best(self, html: str) -> StructuredEventData | None:
        candidates: list[StructuredEventData] = []
        for raw_block in _SCRIPT_JSON_LD.findall(html):
            block = unescape(raw_block.strip())
            if not block:
                continue
            try:
                payload = json.loads(block)
            except json.JSONDecodeError:
                continue
            candidates.extend(self._walk(payload))

        if not candidates:
            return None

        return max(candidates, key=self._candidate_score)

    def _walk(self, node) -> list[StructuredEventData]:
        if isinstance(node, list):
            items: list[StructuredEventData] = []
            for item in node:
                items.extend(self._walk(item))
            return items

        if not isinstance(node, dict):
            return []

        if self._is_event_type(node.get("@type")):
            parsed = self._parse_event_node(node)
            return [parsed] if parsed else []

        results: list[StructuredEventData] = []
        graph = node.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                results.extend(self._walk(item))

        for value in node.values():
            if isinstance(value, (dict, list)):
                results.extend(self._walk(value))
        return results

    def _is_event_type(self, value) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return "event" in value.lower()
        if isinstance(value, list):
            return any(isinstance(item, str) and "event" in item.lower() for item in value)
        return False

    def _parse_event_node(self, node: dict) -> StructuredEventData | None:
        location = node.get("location") or {}
        if isinstance(location, list):
            location = location[0] if location else {}

        address = location.get("address") if isinstance(location, dict) else {}
        if isinstance(address, str):
            city = address
            country = None
        elif isinstance(address, dict):
            city = address.get("addressLocality") or address.get("locality")
            country = address.get("addressCountry")
        else:
            city = location.get("name") if isinstance(location, dict) else None
            country = None

        offers = node.get("offers")
        is_free = self._parse_free(offers)
        start = self._parse_date(node.get("startDate"))
        end = self._parse_date(node.get("endDate"))

        organizer = node.get("organizer")
        organizer_name = None
        if isinstance(organizer, dict):
            organizer_name = organizer.get("name")
        elif isinstance(organizer, str):
            organizer_name = organizer

        return StructuredEventData(
            name=node.get("name"),
            start_date=start,
            end_date=end,
            city=city,
            country=country if isinstance(country, str) else None,
            is_free=is_free,
            description=node.get("description"),
            organizer=organizer_name,
            event_type_hint=self._event_type_hint(node.get("@type")),
        )

    def _parse_free(self, offers) -> bool | None:
        if offers is None:
            return None
        if isinstance(offers, list):
            if not offers:
                return None
            return self._parse_free(offers[0])
        if not isinstance(offers, dict):
            return None

        price = offers.get("price")
        if price is not None:
            try:
                return float(str(price).replace(",", ".")) == 0.0
            except ValueError:
                pass

        availability = str(offers.get("availability", "")).lower()
        if "free" in availability:
            return True
        return None

    def _parse_date(self, value) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        cleaned = value.strip()
        if cleaned[:10].count("-") == 2:
            try:
                parts = cleaned[:10].split("-")
                return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                return None
        return None

    def _event_type_hint(self, event_type) -> str | None:
        if isinstance(event_type, str):
            lowered = event_type.lower()
            if "business" in lowered:
                return "conference"
            if "festival" in lowered:
                return "festival"
        return None

    def _candidate_score(self, item: StructuredEventData) -> int:
        score = 0
        if item.name:
            score += 2
        if item.start_date:
            score += 3
        if item.city:
            score += 2
        if item.is_free is not None:
            score += 1
        return score
