import pytest

from app.infrastructure.search.fake_provider import FakeSearchProvider


@pytest.mark.asyncio
async def test_fake_search_provider_returns_results():
    provider = FakeSearchProvider()
    results = await provider.search("конференция Минск 2026", limit=5)
    assert len(results) > 0
    assert all(result.title for result in results)
    assert all(result.link for result in results)
    assert all(result.source_domain for result in results)


@pytest.mark.asyncio
async def test_fake_search_provider_respects_limit():
    provider = FakeSearchProvider()
    results = await provider.search("любой запрос", limit=2)
    assert len(results) <= 2
