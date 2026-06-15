import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto.search import EventFilterDTO, build_shortlist_filters
from app.application.tasks.enrichment import run_pending_enrichment
from app.application.services.event_candidate_service import EventCandidateService
from app.application.services.search_query_service import SearchQueryService
from app.application.services.search_run_service import SearchRunService
from app.application.use_cases.run_search import RunSearchUseCase
from app.infrastructure.db.session import get_db_session
from app.core.scoring_config import get_scoring_rules
from app.domain.services.lead_time_validator import LeadTimeValidator
from app.infrastructure.factory import (
    create_enrich_event_use_case,
    create_event_candidate_service,
    create_run_search_use_case,
    create_score_event_use_case,
    create_search_query_service,
    create_search_run_service,
)
from app.infrastructure.db.repositories import EventCandidateRepository

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/presentation/web/templates")


def _optional_int(value: str | None) -> int | None:
    if value is None or not str(value).strip():
        return None
    return int(value)


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/events", status_code=302)


@router.get("/events/shortlist", response_class=HTMLResponse)
async def shortlist_page(
    request: Request,
    enriching: str | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    service = create_event_candidate_service(session)
    repo = EventCandidateRepository(session)
    rules = get_scoring_rules()
    events = await service.list_events(build_shortlist_filters())
    lead_time = LeadTimeValidator(rules)
    for event in events:
        days, enough = lead_time.evaluate(event.event_date)
        event.lead_time_days = days
        event.is_enough_lead_time = enough
    pending_count = await repo.count_pending_enrichment()
    return templates.TemplateResponse(
        request,
        "shortlist.html",
        {
            "active_nav": "shortlist",
            "events": events,
            "min_score": rules.shortlist_min_score,
            "min_lead_time_weeks": rules.min_lead_time_weeks,
            "pending_count": pending_count,
            "enriching": enriching == "1",
        },
    )


@router.get("/events", response_class=HTMLResponse)
async def events_page(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    status: str | None = None,
    category: str | None = None,
    source_domain: str | None = None,
    query: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    min_score: str | None = None,
    is_minsk: str | None = None,
    is_free: str | None = None,
    event_type: str | None = None,
    sort_by_score: str | None = None,
) -> HTMLResponse:
    service = create_event_candidate_service(session)
    repo = EventCandidateRepository(session)

    created_from_dt = datetime.fromisoformat(created_from) if created_from else None
    created_to_dt = datetime.fromisoformat(created_to) if created_to else None

    filters = EventFilterDTO(
        status=status or None,
        category=category or None,
        source_domain=source_domain or None,
        source_query=query or None,
        created_from=created_from_dt,
        created_to=created_to_dt,
        min_score=_optional_int(min_score),
        is_minsk=True if is_minsk == "1" else False if is_minsk == "0" else None,
        is_free=True if is_free == "1" else False if is_free == "0" else None,
        event_type=event_type or None,
        sort_by_score=sort_by_score == "1",
        limit=200,
    )
    events = await service.list_events(filters)
    categories = await repo.list_distinct_values("category")
    domains = await repo.list_distinct_values("source_domain")
    queries = await repo.list_distinct_values("source_query")

    return templates.TemplateResponse(
        request,
        "events.html",
        {
            "active_nav": "events",
            "events": events,
            "filters": {
                "status": status or "",
                "category": category or "",
                "source_domain": source_domain or "",
                "query": query or "",
                "created_from": created_from or "",
                "created_to": created_to or "",
                "min_score": min_score or "",
                "is_minsk": is_minsk or "",
                "is_free": is_free or "",
                "event_type": event_type or "",
                "sort_by_score": sort_by_score or "",
            },
            "categories": categories,
            "domains": domains,
            "queries": queries,
        },
    )


@router.get("/events/{event_id}", response_class=HTMLResponse)
async def event_detail_page(
    request: Request,
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    service = create_event_candidate_service(session)
    event = await service.get_event(event_id)
    return templates.TemplateResponse(
        request,
        "event_detail.html",
        {"active_nav": "events", "event": event},
    )


@router.post("/events/{event_id}/enrich", include_in_schema=False)
async def event_enrich_form(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    enrich_use_case = create_enrich_event_use_case(session)
    score_use_case = create_score_event_use_case(session)
    try:
        await enrich_use_case.enrich_event(event_id)
        await score_use_case.score_event(event_id)
    except Exception:
        pass
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@router.post("/events/{event_id}/review", include_in_schema=False)
async def event_review_form(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    status: str = Form(...),
    comment: str = Form(default=""),
    reviewed_by: str = Form(default=""),
) -> RedirectResponse:
    service = create_event_candidate_service(session)
    await service.review_event(
        event_id,
        status=status,
        comment=comment or None,
        reviewed_by=reviewed_by or None,
    )
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@router.get("/search-queries", response_class=HTMLResponse)
async def search_queries_page(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    service = create_search_query_service(session)
    queries = await service.list_queries()
    pending_count = await EventCandidateRepository(session).count_pending_enrichment()
    return templates.TemplateResponse(
        request,
        "search_queries.html",
        {"active_nav": "queries", "queries": queries, "pending_count": pending_count},
    )


@router.get("/search-queries/new", response_class=HTMLResponse)
async def search_query_new_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "search_query_form.html",
        {"active_nav": "queries"},
    )


@router.post("/search-queries/new", include_in_schema=False)
async def search_query_create_form(
    session: AsyncSession = Depends(get_db_session),
    query_text: str = Form(...),
    category: str = Form(default=""),
    is_active: str = Form(default="on"),
) -> RedirectResponse:
    service = create_search_query_service(session)
    await service.create_query(
        query_text=query_text,
        category=category or None,
        is_active=is_active == "on",
    )
    return RedirectResponse(url="/search-queries", status_code=303)


@router.post("/search-queries/{query_id}/toggle", include_in_schema=False)
async def search_query_toggle(
    query_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    service = create_search_query_service(session)
    query = await service.get_query(query_id)
    await service.update_query(query_id, is_active=not query.is_active)
    return RedirectResponse(url="/search-queries", status_code=303)


@router.post("/search-queries/{query_id}/run", include_in_schema=False)
async def search_query_run(
    query_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    use_case = create_run_search_use_case(session)
    await use_case.run_single(query_id)
    return RedirectResponse(url="/search-runs", status_code=303)


@router.post("/search-queries/run-all", include_in_schema=False)
async def search_queries_run_all(
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    use_case = create_run_search_use_case(session)
    await use_case.run_all_active()
    return RedirectResponse(url="/search-runs", status_code=303)


@router.post("/search-queries/enrich-pending", include_in_schema=False)
async def search_queries_enrich_pending(
    background_tasks: BackgroundTasks,
) -> RedirectResponse:
    background_tasks.add_task(run_pending_enrichment)
    return RedirectResponse(url="/events/shortlist?enriching=1", status_code=303)


@router.get("/search-runs", response_class=HTMLResponse)
async def search_runs_page(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    service = create_search_run_service(session)
    runs = await service.list_runs(limit=100)
    return templates.TemplateResponse(
        request,
        "search_runs.html",
        {"active_nav": "runs", "runs": runs},
    )
