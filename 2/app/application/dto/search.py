import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.scoring_config import get_scoring_rules
from app.domain.enums import EnrichmentStatus


@dataclass
class RunSearchResultDTO:
    search_run_id: uuid.UUID
    status: str
    total_results: int
    new_events_count: int
    duplicate_count: int
    error_message: str | None = None


@dataclass
class EventFilterDTO:
    status: str | None = None
    category: str | None = None
    source_domain: str | None = None
    source_query: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    min_score: int | None = None
    is_minsk: bool | None = None
    is_free: bool | None = None
    event_type: str | None = None
    enrichment_status: str | None = None
    event_date_min: datetime | None = None
    include_unknown_event_date: bool = False
    shortlist_only: bool = False
    sort_by_score: bool = False
    limit: int = 100
    offset: int = 0


def build_shortlist_filters(*, limit: int = 100, offset: int = 0) -> EventFilterDTO:
    """Events Onliner can still join by date and that match scoring criteria."""
    rules = get_scoring_rules()
    now = datetime.now(timezone.utc)
    min_event_date = now + timedelta(days=rules.min_lead_time_weeks * 7)
    return EventFilterDTO(
        min_score=rules.shortlist_min_score,
        enrichment_status=EnrichmentStatus.COMPLETED.value,
        event_date_min=min_event_date,
        include_unknown_event_date=True,
        shortlist_only=True,
        sort_by_score=True,
        limit=limit,
        offset=offset,
    )
