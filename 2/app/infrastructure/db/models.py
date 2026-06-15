import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


class SearchQueryModel(Base):
    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_text: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SearchRunModel(Base):
    __tablename__ = "search_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_results: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_events_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    event_candidates: Mapped[list["EventCandidateModel"]] = relationship(
        back_populates="search_run",
    )


class EventCandidateModel(Base):
    __tablename__ = "event_candidates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    relevance_status: Mapped[str] = mapped_column(
        String(20),
        default="new",
        nullable=False,
        index=True,
    )
    source_query: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    search_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("search_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    duplicate_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    is_minsk: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    estimated_attendance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attendance_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    theme_tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    is_free: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ticket_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_recurring: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    edition_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parent_event_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    partner_participation_possible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    partner_formats: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    organizer_benefits: Mapped[str | None] = mapped_column(Text, nullable=True)
    onliner_fit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trend_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    enrichment_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
    )
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    page_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_fetch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_enough_lead_time: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    search_run: Mapped[SearchRunModel] = relationship(back_populates="event_candidates")
    reviews: Mapped[list["EventReviewModel"]] = relationship(
        back_populates="event_candidate",
        cascade="all, delete-orphan",
    )


class EventReviewModel(Base):
    __tablename__ = "event_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("event_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    event_candidate: Mapped[EventCandidateModel] = relationship(back_populates="reviews")
