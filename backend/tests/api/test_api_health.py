"""Tests for /api/v1/health endpoint."""

from fastapi.testclient import TestClient

from aegis.api.app import app

client = TestClient(app)


def test_health_returns_200():
    """GET /api/v1/health should return 200 with status ok."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_health_response_schema():
    """Health response should match HealthResponse schema."""
    response = client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
