"""Tests for all API routes returning correct schemas."""

from fastapi.testclient import TestClient

from aegis.api.app import app

client = TestClient(app)


def test_pipeline_latest_returns_200():
    """GET /api/v1/pipeline/latest should return 200."""
    response = client.get("/api/v1/pipeline/latest")
    assert response.status_code == 200
    data = response.json()
    assert "pipeline_id" in data
    assert "recommendations" in data


def test_pipeline_run_returns_200():
    """POST /api/v1/pipeline/run should return 200."""
    response = client.post("/api/v1/pipeline/run", json={"tickers": ["QQQ"], "mode": "full"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert "pipeline_id" in data


def test_positions_returns_200():
    """GET /api/v1/positions should return 200 with list."""
    response = client.get("/api/v1/positions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_recommendations_returns_200():
    """GET /api/v1/recommendations should return 200 with list."""
    response = client.get("/api/v1/recommendations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_triggers_list_returns_200():
    """GET /api/v1/triggers should return 200 with list."""
    response = client.get("/api/v1/triggers")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_triggers_create_returns_200():
    """POST /api/v1/triggers should return 200."""
    response = client.post(
        "/api/v1/triggers", json={"ticker": "QQQ", "condition": "price > 500"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "QQQ"


def test_triggers_delete_returns_200():
    """DELETE /api/v1/triggers/{id} should return 200."""
    response = client.delete("/api/v1/triggers/1")
    assert response.status_code == 200
    assert response.json() == {"deleted": True}


def test_agents_returns_200():
    """GET /api/v1/agents should return 200 with list."""
    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
