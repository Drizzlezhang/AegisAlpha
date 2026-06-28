"""Tests for KOL REST API routes — sources, calls, and attribution report."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from aegis.api.app import app
from aegis.api.deps import get_attribution_service, get_kol_store


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_kol_source(
    source_id: int = 1,
    name: str = "test_kol",
    platform: str = "x",
    handle: str = "testuser",
    reliability: float = 0.7,
    total_calls: int = 10,
    successful_calls: int = 6,
    enabled: bool = True,
) -> MagicMock:
    src = MagicMock()
    src.id = source_id
    src.name = name
    src.platform = platform
    src.handle = handle
    src.reliability_score = reliability
    src.total_calls = total_calls
    src.successful_calls = successful_calls
    src.enabled = enabled
    src.created_at = None
    return src


def _mock_kol_call(
    call_id: int = 1,
    kol_source_id: int = 1,
    ticker: str = "QQQ",
    direction: str = "bullish",
    call_price: float = 450.0,
    attribution_status: str = "pending",
    pnl_30d: float | None = None,
    pnl_60d: float | None = None,
) -> MagicMock:
    call = MagicMock()
    call.id = call_id
    call.kol_source_id = kol_source_id
    call.ticker = ticker
    call.direction = direction
    call.call_date = None
    call.call_price = call_price
    call.attribution_status = attribution_status
    call.pnl_30d = pnl_30d
    call.pnl_60d = pnl_60d
    call.source_url = ""
    call.content_snippet = ""
    call.created_at = None
    return call


def _make_mock_kol_store() -> MagicMock:
    """Build a mock KOLStore with all async methods."""
    store = MagicMock()
    store.list_sources = AsyncMock(
        return_value=[_mock_kol_source(source_id=1), _mock_kol_source(source_id=2)]
    )
    store.get_source = AsyncMock(return_value=_mock_kol_source(source_id=1))
    store.create_source = AsyncMock(return_value=3)
    store.update_source = AsyncMock()
    store.get_calls_by_ticker = AsyncMock(
        return_value=[_mock_kol_call(call_id=1), _mock_kol_call(call_id=2)]
    )
    store.get_pending_attribution = AsyncMock(return_value=[])
    return store


def _make_mock_attribution_service() -> MagicMock:
    """Build a mock KOLAttributionService."""
    svc = MagicMock()
    svc.get_attribution_report = AsyncMock(
        return_value={
            "total_calls": 100,
            "validated": 60,
            "invalidated": 30,
            "pending": 10,
            "accuracy_pct": 60.0,
        }
    )
    return svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_kol_deps() -> MagicMock:
    """Override KOL dependencies via FastAPI dependency_overrides."""
    mock_store = _make_mock_kol_store()
    mock_attribution = _make_mock_attribution_service()
    app.dependency_overrides[get_kol_store] = lambda: mock_store
    app.dependency_overrides[get_attribution_service] = lambda: mock_attribution
    yield mock_store, mock_attribution
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Source endpoints
# ---------------------------------------------------------------------------


class TestKOLSourcesAPI:
    def test_list_sources(self, client: TestClient) -> None:
        """GET /api/v1/kol/sources should return list of sources."""
        response = client.get("/api/v1/kol/sources")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["id"] == 1
        assert data["items"][0]["name"] == "test_kol"

    def test_list_sources_disabled(self, client: TestClient, mock_kol_deps: tuple) -> None:
        """GET /api/v1/kol/sources?enabled_only=false should return all."""
        mock_store, _ = mock_kol_deps
        mock_store.list_sources = AsyncMock(
            return_value=[_mock_kol_source(enabled=False)]
        )
        response = client.get("/api/v1/kol/sources?enabled_only=false")
        assert response.status_code == 200
        mock_store.list_sources.assert_called_once_with(enabled_only=False)

    def test_get_source_found(self, client: TestClient) -> None:
        """GET /api/v1/kol/sources/{id} should return source."""
        response = client.get("/api/v1/kol/sources/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["platform"] == "x"

    def test_get_source_not_found(self, client: TestClient, mock_kol_deps: tuple) -> None:
        """GET /api/v1/kol/sources/{id} should return 404."""
        mock_store, _ = mock_kol_deps
        mock_store.get_source = AsyncMock(return_value=None)
        response = client.get("/api/v1/kol/sources/999")
        assert response.status_code == 404

    def test_create_source(self, client: TestClient) -> None:
        """POST /api/v1/kol/sources should create source."""
        response = client.post(
            "/api/v1/kol/sources",
            json={"name": "new_kol", "platform": "x", "handle": "newuser"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 3

    def test_create_source_invalid_platform(self, client: TestClient) -> None:
        """POST /api/v1/kol/sources with invalid platform should return 422."""
        response = client.post(
            "/api/v1/kol/sources",
            json={"name": "bad", "platform": "invalid", "handle": "user"},
        )
        assert response.status_code == 422

    def test_update_source(self, client: TestClient, mock_kol_deps: tuple) -> None:
        """PATCH /api/v1/kol/sources/{id} should update source."""
        mock_store, _ = mock_kol_deps
        response = client.patch(
            "/api/v1/kol/sources/1",
            json={"enabled": False},
        )
        assert response.status_code == 200
        mock_store.update_source.assert_called_once_with(1, {"enabled": False})

    def test_update_source_not_found(self, client: TestClient, mock_kol_deps: tuple) -> None:
        """PATCH /api/v1/kol/sources/{id} should return 404."""
        mock_store, _ = mock_kol_deps
        mock_store.get_source = AsyncMock(return_value=None)
        response = client.patch(
            "/api/v1/kol/sources/999",
            json={"enabled": False},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Call endpoints
# ---------------------------------------------------------------------------


class TestKOLCallsAPI:
    def test_list_calls_by_ticker(self, client: TestClient) -> None:
        """GET /api/v1/kol/calls?ticker=QQQ should return calls."""
        response = client.get("/api/v1/kol/calls?ticker=QQQ")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    def test_list_calls_with_status_filter(self, client: TestClient, mock_kol_deps: tuple) -> None:
        """GET /api/v1/kol/calls?status=validated should filter."""
        mock_store, _ = mock_kol_deps
        mock_store.get_calls_by_ticker = AsyncMock(
            return_value=[
                _mock_kol_call(call_id=1, attribution_status="validated"),
                _mock_kol_call(call_id=2, attribution_status="pending"),
            ]
        )
        response = client.get("/api/v1/kol/calls?ticker=QQQ&status=validated")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["attribution_status"] == "validated"

    def test_list_calls_invalid_status(self, client: TestClient) -> None:
        """GET /api/v1/kol/calls?status=unknown should return 422."""
        response = client.get("/api/v1/kol/calls?status=unknown")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Attribution report endpoint
# ---------------------------------------------------------------------------


class TestKOLAttributionAPI:
    def test_get_attribution_report(self, client: TestClient) -> None:
        """GET /api/v1/kol/attribution/report should return stats."""
        response = client.get("/api/v1/kol/attribution/report")
        assert response.status_code == 200
        data = response.json()
        assert data["total_calls"] == 100
        assert data["accuracy_pct"] == 60.0

    def test_get_attribution_report_with_source(
        self, client: TestClient, mock_kol_deps: tuple
    ) -> None:
        """GET /api/v1/kol/attribution/report?source_id=1 should filter."""
        _, mock_attribution = mock_kol_deps
        mock_attribution.get_attribution_report = AsyncMock(
            return_value={
                "total_calls": 50,
                "validated": 30,
                "invalidated": 15,
                "pending": 5,
                "accuracy_pct": 60.0,
                "source": {"name": "test_kol", "reliability_score": 0.75},
            }
        )
        response = client.get("/api/v1/kol/attribution/report?source_id=1")
        assert response.status_code == 200
        data = response.json()
        assert "source" in data
        assert data["source"]["name"] == "test_kol"
