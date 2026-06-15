import pytest


@pytest.mark.asyncio
async def test_health_endpoint(api_client):
    response = await api_client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload


@pytest.mark.asyncio
async def test_create_search_query(api_client):
    response = await api_client.post(
        "/api/v1/search-queries",
        json={"query_text": "новый запрос тест", "category": "тест"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["query_text"] == "новый запрос тест"
    assert payload["is_active"] is True


@pytest.mark.asyncio
async def test_run_search(api_client):
    response = await api_client.post("/api/v1/search-runs")
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["new_events_count"] >= 0


@pytest.mark.asyncio
async def test_review_event_changes_status(api_client):
    run_response = await api_client.post("/api/v1/search-runs")
    assert run_response.status_code == 201

    events_response = await api_client.get("/api/v1/events")
    assert events_response.status_code == 200
    events = events_response.json()
    assert events

    event_id = events[0]["id"]
    review_response = await api_client.patch(
        f"/api/v1/events/{event_id}/review",
        json={"status": "approved", "comment": "Подходит для инфопартнёрства"},
    )
    assert review_response.status_code == 200
    assert review_response.json()["relevance_status"] == "approved"


@pytest.mark.asyncio
async def test_empty_query_validation(api_client):
    response = await api_client.post(
        "/api/v1/search-queries",
        json={"query_text": "   "},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_invalid_event_status(api_client):
    run_response = await api_client.post("/api/v1/search-runs")
    events = (await api_client.get("/api/v1/events")).json()
    event_id = events[0]["id"]

    response = await api_client.patch(
        f"/api/v1/events/{event_id}/review",
        json={"status": "invalid"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_EVENT_STATUS"
