import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto.search import EventFilterDTO
from app.domain.entities import EventCandidateEntity, SearchQueryEntity, SearchRunEntity
from app.domain.enums import RelevanceStatus, SearchRunStatus
from app.infrastructure.db.models import (
    EventCandidateModel,
    EventReviewModel,
    SearchQueryModel,
    SearchRunModel,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SearchQueryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: SearchQueryModel) -> SearchQueryEntity:
        return SearchQueryEntity(
            id=model.id,
            query_text=model.query_text,
            category=model.category,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self, *, active_only: bool = False) -> list[SearchQueryEntity]:
        stmt = select(SearchQueryModel).order_by(SearchQueryModel.id)
        if active_only:
            stmt = stmt.where(SearchQueryModel.is_active.is_(True))
        result = await self._session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]

    async def get_by_id(self, query_id: int) -> SearchQueryEntity | None:
        model = await self._session.get(SearchQueryModel, query_id)
        return self._to_entity(model) if model else None

    async def create(
        self,
        *,
        query_text: str,
        category: str | None,
        is_active: bool,
    ) -> SearchQueryEntity:
        model = SearchQueryModel(
            query_text=query_text,
            category=category,
            is_active=is_active,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def update(self, entity: SearchQueryEntity) -> SearchQueryEntity:
        model = await self._session.get(SearchQueryModel, entity.id)
        if model is None:
            return entity
        model.query_text = entity.query_text
        model.category = entity.category
        model.is_active = entity.is_active
        model.updated_at = _utcnow()
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, query_id: int) -> None:
        model = await self._session.get(SearchQueryModel, query_id)
        if model:
            await self._session.delete(model)

    async def is_used_in_search_run(self, query_text: str) -> bool:
        stmt = (
            select(func.count())
            .select_from(EventCandidateModel)
            .where(EventCandidateModel.source_query == query_text)
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0


class SearchRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: SearchRunModel) -> SearchRunEntity:
        return SearchRunEntity(
            id=model.id,
            status=model.status,
            started_at=model.started_at,
            completed_at=model.completed_at,
            total_results=model.total_results,
            new_events_count=model.new_events_count,
            duplicate_count=model.duplicate_count,
            error_message=model.error_message,
        )

    async def create(self, *, status: str) -> SearchRunEntity:
        model = SearchRunModel(status=status)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def finalize(self, entity: SearchRunEntity) -> SearchRunEntity:
        model = await self._session.get(SearchRunModel, entity.id)
        if model is None:
            return entity
        model.status = entity.status
        model.total_results = entity.total_results
        model.new_events_count = entity.new_events_count
        model.duplicate_count = entity.duplicate_count
        model.error_message = entity.error_message
        if entity.status in {SearchRunStatus.COMPLETED.value, SearchRunStatus.FAILED.value}:
            model.completed_at = _utcnow()
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, run_id: uuid.UUID) -> SearchRunEntity | None:
        model = await self._session.get(SearchRunModel, run_id)
        return self._to_entity(model) if model else None

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[SearchRunEntity]:
        stmt = (
            select(SearchRunModel)
            .order_by(SearchRunModel.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]


class EventCandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    @asynccontextmanager
    async def nested_transaction(self) -> AsyncIterator[None]:
        async with self._session.begin_nested():
            yield

    def _to_entity(self, model: EventCandidateModel) -> EventCandidateEntity:
        return EventCandidateEntity(
            id=model.id,
            title=model.title,
            description=model.description,
            url=model.url,
            source_domain=model.source_domain,
            city=model.city,
            country=model.country,
            event_date=model.event_date,
            category=model.category,
            relevance_status=model.relevance_status,
            source_query=model.source_query,
            search_run_id=model.search_run_id,
            duplicate_key=model.duplicate_key,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_minsk=model.is_minsk,
            estimated_attendance=model.estimated_attendance,
            attendance_source=model.attendance_source,
            event_type=model.event_type,
            theme_tags=model.theme_tags or [],
            is_free=model.is_free,
            ticket_info=model.ticket_info,
            is_recurring=model.is_recurring,
            edition_label=model.edition_label,
            parent_event_key=model.parent_event_key,
            partner_participation_possible=model.partner_participation_possible,
            partner_formats=model.partner_formats or [],
            organizer_benefits=model.organizer_benefits,
            onliner_fit_score=model.onliner_fit_score,
            trend_score=model.trend_score,
            relevance_score=model.relevance_score,
            score_breakdown=model.score_breakdown or {},
            enrichment_status=model.enrichment_status,
            enriched_at=model.enriched_at,
            page_text=model.page_text,
            page_fetch_error=model.page_fetch_error,
            lead_time_days=model.lead_time_days,
            is_enough_lead_time=model.is_enough_lead_time,
        )

    async def get_by_id(self, event_id: uuid.UUID) -> EventCandidateEntity | None:
        model = await self._session.get(EventCandidateModel, event_id)
        return self._to_entity(model) if model else None

    async def get_by_duplicate_key(self, duplicate_key: str) -> EventCandidateEntity | None:
        stmt = select(EventCandidateModel).where(EventCandidateModel.duplicate_key == duplicate_key)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def create(
        self,
        *,
        title: str,
        description: str | None,
        url: str,
        source_domain: str,
        source_query: str,
        search_run_id: uuid.UUID,
        duplicate_key: str,
        category: str | None = None,
        city: str | None = None,
        country: str | None = None,
        event_date: datetime | None = None,
    ) -> EventCandidateEntity:
        model = EventCandidateModel(
            title=title,
            description=description,
            url=url,
            source_domain=source_domain.lower(),
            source_query=source_query,
            search_run_id=search_run_id,
            duplicate_key=duplicate_key,
            category=category,
            city=city,
            country=country,
            event_date=event_date,
            relevance_status=RelevanceStatus.NEW.value,
            enrichment_status="pending",
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def update(self, entity: EventCandidateEntity) -> EventCandidateEntity:
        model = await self._session.get(EventCandidateModel, entity.id)
        if model is None:
            return entity
        model.relevance_status = entity.relevance_status
        model.updated_at = entity.updated_at
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def list_filtered(self, filters: EventFilterDTO) -> list[EventCandidateEntity]:
        stmt = select(EventCandidateModel)

        if filters.shortlist_only:
            stmt = stmt.order_by(
                EventCandidateModel.relevance_score.desc().nullslast(),
                EventCandidateModel.event_date.asc().nullslast(),
            )
        elif filters.sort_by_score:
            stmt = stmt.order_by(
                EventCandidateModel.relevance_score.desc().nullslast(),
                EventCandidateModel.created_at.desc(),
            )
        else:
            stmt = stmt.order_by(EventCandidateModel.created_at.desc())

        if filters.status:
            stmt = stmt.where(EventCandidateModel.relevance_status == filters.status)
        if filters.category:
            stmt = stmt.where(EventCandidateModel.category == filters.category)
        if filters.source_domain:
            stmt = stmt.where(
                EventCandidateModel.source_domain.ilike(f"%{filters.source_domain.lower()}%")
            )
        if filters.source_query:
            stmt = stmt.where(EventCandidateModel.source_query == filters.source_query)
        if filters.created_from:
            stmt = stmt.where(EventCandidateModel.created_at >= filters.created_from)
        if filters.created_to:
            stmt = stmt.where(EventCandidateModel.created_at <= filters.created_to)
        if filters.min_score is not None:
            stmt = stmt.where(EventCandidateModel.relevance_score >= filters.min_score)
        if filters.is_minsk is not None:
            stmt = stmt.where(EventCandidateModel.is_minsk.is_(filters.is_minsk))
        if filters.is_free is not None:
            stmt = stmt.where(EventCandidateModel.is_free.is_(filters.is_free))
        if filters.event_type:
            stmt = stmt.where(EventCandidateModel.event_type == filters.event_type)
        if filters.enrichment_status:
            stmt = stmt.where(EventCandidateModel.enrichment_status == filters.enrichment_status)
        if filters.event_date_min is not None:
            if filters.include_unknown_event_date:
                stmt = stmt.where(
                    or_(
                        EventCandidateModel.event_date.is_(None),
                        EventCandidateModel.event_date >= filters.event_date_min,
                    )
                )
            else:
                stmt = stmt.where(EventCandidateModel.event_date >= filters.event_date_min)
        if filters.shortlist_only:
            stmt = stmt.where(EventCandidateModel.relevance_status != RelevanceStatus.REJECTED.value)
            stmt = stmt.where(EventCandidateModel.is_minsk.is_(True))

        stmt = stmt.limit(filters.limit).offset(filters.offset)
        result = await self._session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]

    async def count_pending_enrichment(self) -> int:
        stmt = (
            select(func.count())
            .select_from(EventCandidateModel)
            .where(EventCandidateModel.enrichment_status.in_(("pending", "failed")))
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_pending(self, *, limit: int = 200) -> list[EventCandidateEntity]:
        stmt = (
            select(EventCandidateModel)
            .where(EventCandidateModel.enrichment_status.in_(("pending", "failed")))
            .order_by(EventCandidateModel.created_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]

    async def list_by_search_run(
        self,
        search_run_id: uuid.UUID,
        *,
        enrichment_status: str | None = None,
    ) -> list[EventCandidateEntity]:
        stmt = select(EventCandidateModel).where(EventCandidateModel.search_run_id == search_run_id)
        if enrichment_status:
            stmt = stmt.where(EventCandidateModel.enrichment_status == enrichment_status)
        result = await self._session.execute(stmt.order_by(EventCandidateModel.created_at))
        return [self._to_entity(row) for row in result.scalars().all()]

    async def find_by_parent_event_key(
        self,
        parent_event_key: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> EventCandidateEntity | None:
        stmt = select(EventCandidateModel).where(
            EventCandidateModel.parent_event_key == parent_event_key,
        )
        if exclude_id is not None:
            stmt = stmt.where(EventCandidateModel.id != exclude_id)
        stmt = stmt.order_by(EventCandidateModel.created_at.desc()).limit(1)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save_enrichment(self, entity: EventCandidateEntity) -> EventCandidateEntity:
        model = await self._session.get(EventCandidateModel, entity.id)
        if model is None:
            return entity
        model.city = entity.city
        model.event_date = entity.event_date
        model.is_minsk = entity.is_minsk
        model.estimated_attendance = entity.estimated_attendance
        model.attendance_source = entity.attendance_source
        model.event_type = entity.event_type
        model.theme_tags = entity.theme_tags
        model.is_free = entity.is_free
        model.ticket_info = entity.ticket_info
        model.is_recurring = entity.is_recurring
        model.edition_label = entity.edition_label
        model.parent_event_key = entity.parent_event_key
        model.partner_participation_possible = entity.partner_participation_possible
        model.partner_formats = entity.partner_formats
        model.organizer_benefits = entity.organizer_benefits
        model.trend_score = entity.trend_score
        model.page_text = entity.page_text[:20000] if entity.page_text else None
        model.page_fetch_error = entity.page_fetch_error
        model.lead_time_days = entity.lead_time_days
        model.is_enough_lead_time = entity.is_enough_lead_time
        model.enrichment_status = entity.enrichment_status
        model.enriched_at = entity.enriched_at
        model.relevance_status = entity.relevance_status
        model.is_minsk = entity.is_minsk
        model.updated_at = entity.updated_at
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def save_scoring(self, entity: EventCandidateEntity) -> EventCandidateEntity:
        model = await self._session.get(EventCandidateModel, entity.id)
        if model is None:
            return entity
        model.relevance_score = entity.relevance_score
        model.score_breakdown = entity.score_breakdown
        model.onliner_fit_score = entity.onliner_fit_score
        model.updated_at = entity.updated_at
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def list_distinct_values(self, field: str) -> list[str]:
        column = getattr(EventCandidateModel, field, None)
        if column is None:
            return []
        stmt = select(column).distinct().where(column.is_not(None)).order_by(column)
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all() if row[0]]


class EventReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        event_candidate_id: uuid.UUID,
        status: str,
        comment: str | None,
        reviewed_by: str | None,
    ) -> None:
        model = EventReviewModel(
            event_candidate_id=event_candidate_id,
            status=status,
            comment=comment,
            reviewed_by=reviewed_by,
        )
        self._session.add(model)
        await self._session.flush()
