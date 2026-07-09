from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="", query="").geturl().rstrip("/")


def duplicate_key(url: str) -> str:
    return hashlib.sha256(normalize_url(url).lower().encode()).hexdigest()[:40]


def source_domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


@dataclass
class EventRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    url: str = ""
    source_domain: str = ""
    description: str | None = None
    enrichment_status: str = "pending"
    relevance_status: str = "new"
    relevance_score: int | None = None
    onliner_fit_score: int | None = None
    is_minsk: bool | None = None
    city: str | None = None
    event_date: datetime | None = None
    estimated_attendance: int | None = None
    is_free: bool | None = None
    is_recurring: bool = False
    partner_participation_possible: bool = False
    partner_formats: list[str] = field(default_factory=list)
    theme_tags: list[str] = field(default_factory=list)
    event_type: str = "other"
    lead_time_days: int | None = None
    is_enough_lead_time: bool | None = None
    trend_score: int = 0
    page_text: str | None = None
    page_fetch_error: str | None = None
    score_breakdown: dict[str, Any] = field(default_factory=dict)
    score_explanations: dict[str, str] = field(default_factory=dict)
    enriched_at: datetime | None = None

    @classmethod
    def from_search_hit(
        cls,
        *,
        title: str,
        url: str,
        description: str | None,
    ) -> EventRecord:
        return cls(
            title=title.strip(),
            url=url,
            source_domain=source_domain(url),
            description=description,
        )


@dataclass
class PipelineProgress:
    phase: str = "starting"
    search_hits: int = 0
    total_candidates: int = 0
    processed: int = 0
    enriched: int = 0
    rejected: int = 0
    failed: int = 0
    catalog_expanded: int = 0
    suitable_count: int = 0
