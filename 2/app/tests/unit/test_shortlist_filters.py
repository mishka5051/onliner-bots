from datetime import datetime, timezone

from app.application.dto.search import build_shortlist_filters
from app.domain.enums import EnrichmentStatus


def test_build_shortlist_filters_uses_score_and_lead_time():
    filters = build_shortlist_filters()
    assert filters.shortlist_only is True
    assert filters.min_score == 50
    assert filters.enrichment_status == EnrichmentStatus.COMPLETED.value
    assert filters.include_unknown_event_date is True
    assert filters.status is None
    assert filters.event_date_min is not None
    assert filters.event_date_min > datetime.now(timezone.utc)
