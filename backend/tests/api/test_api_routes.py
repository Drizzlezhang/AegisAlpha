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
    import uuid

    unique_ticker = f"TEST-{uuid.uuid4().hex[:6]}"
    response = client.post(
        "/api/v1/triggers",
        json={
            "ticker": unique_ticker,
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 500},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == unique_ticker


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


def test_flows_etf_returns_200():
    """GET /api/v1/flows/etf should return 200 with list."""
    response = client.get("/api/v1/flows/etf")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "ticker" in data[0]
    assert "net_flow" in data[0]


def test_flows_sector_returns_200():
    """GET /api/v1/flows/sector should return 200 with list."""
    response = client.get("/api/v1/flows/sector")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "sector" in data[0]
    assert "rotation_score" in data[0]


def test_flows_smart_money_returns_200():
    """GET /api/v1/flows/smart-money/{ticker} should return 200."""
    response = client.get("/api/v1/flows/smart-money/QQQ")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "QQQ"
    assert "score" in data
    assert "direction" in data


def test_portfolio_health_returns_200():
    """GET /api/v1/portfolio/health should return 200."""
    response = client.get("/api/v1/portfolio/health")
    assert response.status_code == 200
    data = response.json()
    assert "health_scores" in data
    assert "alerts" in data


def test_portfolio_delta_dollars_returns_200():
    """GET /api/v1/portfolio/delta-dollars should return 200."""
    response = client.get("/api/v1/portfolio/delta-dollars")
    assert response.status_code == 200
    data = response.json()
    assert "total_delta_dollars" in data
    assert "budget_pct" in data


def test_pipeline_trigger_returns_200():
    """POST /api/v1/pipeline/trigger should return 200."""
    response = client.post(
        "/api/v1/pipeline/trigger",
        json={"tickers": ["QQQ"], "mode": "full"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["mode"] == "full"
    assert "pipeline_id" in data


def test_pipeline_trigger_lightweight_returns_200():
    """POST /api/v1/pipeline/trigger with lightweight mode should return 200."""
    response = client.post(
        "/api/v1/pipeline/trigger",
        json={"tickers": ["QQQ"], "mode": "lightweight"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["mode"] == "lightweight"
