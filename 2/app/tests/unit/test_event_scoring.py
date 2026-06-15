from datetime import datetime, timedelta, timezone
import uuid

from app.domain.entities import EventCandidateEntity
from app.domain.services.event_scoring import EventScoringService


def _event(**overrides) -> EventCandidateEntity:
    base = EventCandidateEntity(
        id=uuid.uuid4(),
        title="IT конференция Минск",
        description="e-commerce и digital",
        url="https://example.com",
        source_domain="example.com",
        city="Минск",
        country="Беларусь",
        event_date=datetime.now(timezone.utc) + timedelta(days=60),
        category="IT",
        relevance_status="new",
        source_query="test",
        search_run_id=uuid.uuid4(),
        duplicate_key="abc",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        is_minsk=True,
        estimated_attendance=5000,
        is_free=True,
        is_recurring=True,
        partner_participation_possible=True,
        is_enough_lead_time=True,
        theme_tags=["technology"],
        trend_score=10,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_high_score_for_ideal_minsk_event():
    result = EventScoringService().score(_event())
    assert result.relevance_score >= 50
    assert "minsk" in result.score_breakdown
    assert "free_entry" in result.score_breakdown


def test_penalty_for_paid_non_minsk_event():
    result = EventScoringService().score(
        _event(is_minsk=False, is_free=False, estimated_attendance=None, is_recurring=False)
    )
    assert result.relevance_score < 50
