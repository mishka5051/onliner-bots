import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import SearchQueryModel
from app.infrastructure.search.fake_provider import FakeSearchProvider
from app.main import create_app


@pytest.fixture
def fake_search_provider() -> FakeSearchProvider:
    return FakeSearchProvider()


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            SearchQueryModel(
                query_text="конференция Минск 2026",
                category="конференция",
                is_active=True,
            )
        )
        session.add(
            SearchQueryModel(
                query_text="IT мероприятие Минск 2026",
                category="IT",
                is_active=True,
            )
        )
        await session.commit()
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("SEARCH_PROVIDER", "fake")
    get_settings.cache_clear()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def seed(session: AsyncSession) -> None:
        session.add(
            SearchQueryModel(
                query_text="конференция Минск 2026",
                category="конференция",
                is_active=True,
            )
        )
        await session.commit()

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    from app.infrastructure.db.session import get_db_session

    app.dependency_overrides[get_db_session] = override_get_db

    async with session_factory() as session:
        await seed(session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    await engine.dispose()
