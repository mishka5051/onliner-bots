from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.search.searxng_provider import SearXngSearchProvider


@pytest.mark.asyncio
async def test_searxng_provider_parses_json_results():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "title": "IT-конференция Минск 2026",
                "url": "https://events.example.by/conf",
                "content": "Крупная конференция для разработчиков",
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.infrastructure.search.searxng_provider.httpx.AsyncClient", return_value=mock_client):
        provider = SearXngSearchProvider(base_url="http://searxng:8080")
        results = await provider.search("конференция Минск 2026", limit=5)

    assert len(results) == 1
    assert results[0].title == "IT-конференция Минск 2026"
    assert results[0].link == "https://events.example.by/conf"
    assert results[0].source_domain == "events.example.by"
    assert results[0].snippet == "Крупная конференция для разработчиков"
