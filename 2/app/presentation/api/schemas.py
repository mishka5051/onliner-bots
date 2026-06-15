import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SearchQueryCreate(BaseModel):
    query_text: str = Field(min_length=1, max_length=512)
    category: str | None = Field(default=None, max_length=100)
    is_active: bool = True


class SearchQueryUpdate(BaseModel):
    query_text: str | None = Field(default=None, min_length=1, max_length=512)
    category: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class SearchQueryResponse(BaseModel):
    id: int
    query_text: str
    category: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SearchRunResponse(BaseModel):
    id: uuid.UUID
    status: str
    started_at: datetime
    completed_at: datetime | None
    total_results: int
    new_events_count: int
    duplicate_count: int
    error_message: str | None

    model_config = {"from_attributes": True}


class RunSearchResponse(BaseModel):
    search_run_id: uuid.UUID
    status: str
    total_results: int
    new_events_count: int
    duplicate_count: int
    error_message: str | None = None


class EventCandidateResponse(BaseModel):
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
    event_type: str | None = None
    theme_tags: list[str] = []
    is_free: bool | None = None
    is_recurring: bool | None = None
    partner_participation_possible: bool | None = None
    relevance_score: int | None = None
    score_breakdown: dict = {}
    enrichment_status: str = "pending"
    lead_time_days: int | None = None
    is_enough_lead_time: bool | None = None
    onliner_fit_score: int | None = None

    model_config = {"from_attributes": True}


class EventReviewRequest(BaseModel):
    status: str
    comment: str | None = None
    reviewed_by: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
