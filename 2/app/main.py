from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.presentation.api.error_handlers import register_error_handlers
from app.presentation.api.routes.events import router as events_router
from app.presentation.api.routes.health import router as health_router
from app.presentation.api.routes.search_queries import router as search_queries_router
from app.presentation.api.routes.search_runs import router as search_runs_router
from app.presentation.web.routes import router as web_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Event search service for Onliner info partnerships",
        lifespan=lifespan,
    )

    register_error_handlers(app)

    static_dir = Path(__file__).parent / "presentation" / "web" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(search_queries_router, prefix="/api/v1")
    app.include_router(search_runs_router, prefix="/api/v1")
    app.include_router(events_router, prefix="/api/v1")
    app.include_router(web_router)

    return app


app = create_app()
