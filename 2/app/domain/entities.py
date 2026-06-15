import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SearchQueryEntity:
    id: int
    query_text: str
    category: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class SearchRunEntity:
    id: uuid.UUID
    status: str
    started_at: datetime
    completed_at: datetime | None
    total_results: int
    new_events_count: int
    duplicate_count: int
    error_message: str | None


@dataclass
class EventCandidateEntity:
    id: uuid.UUID
    title: str
    description: str | None
    url: str
    source_domain: str
    city: str | None
    country: str | None
    event_date: datetime | None
    category: str | None
    relevance_status: str
    source_query: str
    search_run_id: uuid.UUID
    duplicate_key: str
    created_at: datetime
    updated_at: datetime
    is_minsk: bool | None = None
    estimated_attendance: int | None = None
    attendance_source: str | None = None
    event_type: str | None = None
    theme_tags: list[str] = field(default_factory=list)
    is_free: bool | None = None
    ticket_info: str | None = None
    is_recurring: bool | None = None
    edition_label: str | None = None
    parent_event_key: str | None = None
    partner_participation_possible: bool | None = None
    partner_formats: list[str] = field(default_factory=list)
    organizer_benefits: str | None = None
    onliner_fit_score: int | None = None
    trend_score: int | None = None
    relevance_score: int | None = None
    score_breakdown: dict[str, Any] = field(default_factory=dict)
    enrichment_status: str = "pending"
    enriched_at: datetime | None = None
    page_text: str | None = None
    page_fetch_error: str | None = None
    lead_time_days: int | None = None
    is_enough_lead_time: bool | None = None
