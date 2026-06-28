"""Tests for Thesis REST API endpoints — 6 endpoints + error handling + pagination."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from aegis.api.app import app
from aegis.api.deps import get_thesis_service


# ---------------------------------------------------------------------------
# Mock ThesisService
# ---------------------------------------------------------------------------


class MockThesisCard:
    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", 1)
        self.ticker = kwargs.get("ticker", "QQQ")
        self.direction = kwargs.get("direction", "long")
        self.entry_mode = kwargs.get("entry_mode", "active_right")
        self.entry_date = kwargs.get("entry_date", datetime(2026, 5, 1, tzinfo=UTC))
        self.entry_price = kwargs.get("entry_price", 450.0)
        self.target_price = kwargs.get("target_price", 500.0)
        self.stop_price = kwargs.get("stop_price", 420.0)
        self.key_assumptions = kwargs.get("key_assumptions", ["QQQ above 200MA"])
        self.thesis_valid_status = kwargs.get("thesis_valid_status", "valid")
        self.re_entry_flagged = kwargs.get("re_entry_flagged", False)
        self.factor_snapshot = kwargs.get("factor_snapshot", {})
        self.close_date = kwargs.get("close_date", None)
        self.close_price = kwargs.get("close_price", None)
        self.actual_pnl_pct = kwargs.get("actual_pnl_pct", None)
        self.judgment_score = kwargs.get("judgment_score", None)
        self.execution_score = kwargs.get("execution_score", None)
        self.close_reason = kwargs.get("close_reason", None)
        self.created_at = kwargs.get("created_at", datetime(2026, 5, 1, tzinfo=UTC))


def _make_card(**kwargs: Any) -> MockThesisCard:
    return MockThesisCard(**kwargs)


def _card_to_dict(card: MockThesisCard) -> dict[str, Any]:
    return {
        "id": card.id,
        "ticker": card.ticker,
        "direction": card.direction,
        "entry_mode": card.entry_mode,
        "entry_date": card.entry_date.isoformat() if card.entry_date else None,
        "entry_price": card.entry_price,
        "target_price": card.target_price,
        "stop_price": card.stop_price,
        "key_assumptions": card.key_assumptions,
        "thesis_valid_status": card.thesis_valid_status,
        "re_entry_flagged": card.re_entry_flagged,
        "factor_snapshot": card.factor_snapshot,
        "close_date": card.close_date.isoformat() if card.close_date else None,
        "close_price": card.close_price,
        "actual_pnl_pct": card.actual_pnl_pct,
        "judgment_score": card.judgment_score,
        "execution_score": card.execution_score,
        "close_reason": card.close_reason,
        "created_at": card.created_at.isoformat() if card.created_at else None,
    }


def _make_mock_service() -> MagicMock:
    """Build a mock ThesisService with all async methods."""
    svc = MagicMock()
    svc._store = MagicMock()
    svc._memory = MagicMock()
    svc._card_to_dict = _card_to_dict

    svc._store.list_all = AsyncMock(return_value=[_make_card(id=1), _make_card(id=2)])
    svc._store.get_by_id = AsyncMock(return_value=_make_card(id=1))
    svc.create_from_recommendation = AsyncMock(return_value=1)
    svc.close_thesis = AsyncMock(return_value={
        "thesis_id": 1,
        "pnl_pct": 0.1111,
        "new_weights": {"trend_phase": 80},
    })
    svc._store.update = AsyncMock()
    svc._memory.read = AsyncMock(return_value=[
        {"data_type": "thesis_validation", "content": {"status": "valid"}},
    ])
    return svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_thesis_service() -> MagicMock:
    """Override get_thesis_service via FastAPI dependency_overrides."""
    mock_svc = _make_mock_service()
    app.dependency_overrides[get_thesis_service] = lambda: mock_svc
    yield mock_svc
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListTheses:
    """GET /api/v1/thesis — list with filters and pagination."""

    def test_list_all(self, client: TestClient) -> None:
        response = client.get("/api/v1/thesis")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert data["limit"] == 50
        assert data["offset"] == 0

    def test_list_with_status_filter(self, client: TestClient) -> None:
        response = client.get("/api/v1/thesis?status=valid")
        assert response.status_code == 200

    def test_list_with_ticker_filter(self, client: TestClient) -> None:
        response = client.get("/api/v1/thesis?ticker=QQQ")
        assert response.status_code == 200

    def test_list_with_direction_filter(self, client: TestClient) -> None:
        response = client.get("/api/v1/thesis?direction=long")
        assert response.status_code == 200

    def test_list_with_pagination(self, client: TestClient) -> None:
        response = client.get("/api/v1/thesis?limit=10&offset=5")
        assert response.status_code == 200

    def test_list_rejects_invalid_status(self, client: TestClient) -> None:
        response = client.get("/api/v1/thesis?status=unknown")
        assert response.status_code == 422

    def test_list_rejects_invalid_limit(self, client: TestClient) -> None:
        response = client.get("/api/v1/thesis?limit=500")
        assert response.status_code == 422


class TestGetThesis:
    """GET /api/v1/thesis/{thesis_id} — single thesis detail."""

    def test_get_existing(self, client: TestClient) -> None:
        response = client.get("/api/v1/thesis/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["ticker"] == "QQQ"

    def test_get_not_found(self, client: TestClient, mock_thesis_service: MagicMock) -> None:
        mock_thesis_service._store.get_by_id = AsyncMock(return_value=None)
        response = client.get("/api/v1/thesis/999")
        assert response.status_code == 404


class TestCreateThesis:
    """POST /api/v1/thesis — manual thesis creation."""

    def test_create_success(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/thesis",
            json={
                "ticker": "QQQ",
                "direction": "long",
                "entry_mode": "active_right",
                "entry_price": 450.0,
                "target_price": 500.0,
                "stop_price": 420.0,
                "key_assumptions": ["QQQ above 200MA"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 1
        assert data["message"] == "Thesis created"

    def test_create_duplicate_active(
        self, client: TestClient, mock_thesis_service: MagicMock
    ) -> None:
        mock_thesis_service.create_from_recommendation = AsyncMock(
            side_effect=ValueError("Active thesis already exists for QQQ")
        )
        response = client.post(
            "/api/v1/thesis",
            json={
                "ticker": "QQQ",
                "direction": "long",
                "entry_price": 450.0,
                "key_assumptions": ["test"],
            },
        )
        assert response.status_code == 409

    def test_create_invalid_direction(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/thesis",
            json={
                "ticker": "QQQ",
                "direction": "invalid_dir",
                "entry_price": 450.0,
                "key_assumptions": ["test"],
            },
        )
        assert response.status_code == 422

    def test_create_invalid_entry_mode(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/thesis",
            json={
                "ticker": "QQQ",
                "direction": "long",
                "entry_mode": "invalid_mode",
                "entry_price": 450.0,
                "key_assumptions": ["test"],
            },
        )
        assert response.status_code == 422

    def test_create_missing_required_fields(self, client: TestClient) -> None:
        response = client.post("/api/v1/thesis", json={"ticker": "QQQ"})
        assert response.status_code == 422


class TestCloseThesis:
    """POST /api/v1/thesis/{thesis_id}/close — close with dual scores."""

    def test_close_success(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/thesis/1/close",
            json={
                "close_price": 500.0,
                "judgment_score": 4,
                "execution_score": 3,
                "close_reason": "target_reached",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["thesis_id"] == 1
        assert "pnl_pct" in data
        assert "new_weights" in data

    def test_close_not_found(
        self, client: TestClient, mock_thesis_service: MagicMock
    ) -> None:
        mock_thesis_service.close_thesis = AsyncMock(
            side_effect=ValueError("Thesis 999 not found")
        )
        response = client.post(
            "/api/v1/thesis/999/close",
            json={
                "close_price": 500.0,
                "judgment_score": 4,
                "execution_score": 3,
                "close_reason": "target_reached",
            },
        )
        assert response.status_code == 400

    def test_close_already_closed(
        self, client: TestClient, mock_thesis_service: MagicMock
    ) -> None:
        mock_thesis_service.close_thesis = AsyncMock(
            side_effect=ValueError("Thesis 1 already closed")
        )
        response = client.post(
            "/api/v1/thesis/1/close",
            json={
                "close_price": 500.0,
                "judgment_score": 4,
                "execution_score": 3,
                "close_reason": "target_reached",
            },
        )
        assert response.status_code == 400

    def test_close_invalid_judgment_score(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/thesis/1/close",
            json={
                "close_price": 500.0,
                "judgment_score": 6,
                "execution_score": 3,
                "close_reason": "target_reached",
            },
        )
        assert response.status_code == 422

    def test_close_invalid_execution_score(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/thesis/1/close",
            json={
                "close_price": 500.0,
                "judgment_score": 4,
                "execution_score": 0,
                "close_reason": "target_reached",
            },
        )
        assert response.status_code == 422

    def test_close_invalid_reason(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/thesis/1/close",
            json={
                "close_price": 500.0,
                "judgment_score": 4,
                "execution_score": 3,
                "close_reason": "invalid_reason",
            },
        )
        assert response.status_code == 422

    def test_close_missing_scores(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/thesis/1/close",
            json={"close_price": 500.0, "close_reason": "manual"},
        )
        assert response.status_code == 422


class TestUpdateThesis:
    """PATCH /api/v1/thesis/{thesis_id} — partial update."""

    def test_update_success(self, client: TestClient) -> None:
        response = client.patch(
            "/api/v1/thesis/1",
            json={"target_price": 520.0, "stop_price": 430.0},
        )
        assert response.status_code == 200
        assert response.json() == {"message": "Updated"}

    def test_update_not_found(
        self, client: TestClient, mock_thesis_service: MagicMock
    ) -> None:
        mock_thesis_service._store.get_by_id = AsyncMock(return_value=None)
        response = client.patch("/api/v1/thesis/999", json={"target_price": 520.0})
        assert response.status_code == 404

    def test_update_closed_thesis(
        self, client: TestClient, mock_thesis_service: MagicMock
    ) -> None:
        mock_thesis_service._store.get_by_id = AsyncMock(
            return_value=_make_card(close_date=datetime(2026, 5, 15, tzinfo=UTC))
        )
        response = client.patch("/api/v1/thesis/1", json={"target_price": 520.0})
        assert response.status_code == 400

    def test_update_empty_body(self, client: TestClient) -> None:
        response = client.patch("/api/v1/thesis/1", json={})
        assert response.status_code == 200
        assert response.json() == {"message": "Updated"}


class TestValidationHistory:
    """GET /api/v1/thesis/{thesis_id}/history — validation history."""

    def test_get_history(self, client: TestClient) -> None:
        response = client.get("/api/v1/thesis/1/history")
        assert response.status_code == 200
        data = response.json()
        assert data["thesis_id"] == 1
        assert "history" in data
        assert len(data["history"]) == 1

    def test_get_history_not_found(
        self, client: TestClient, mock_thesis_service: MagicMock
    ) -> None:
        mock_thesis_service._store.get_by_id = AsyncMock(return_value=None)
        response = client.get("/api/v1/thesis/999/history")
        assert response.status_code == 404
