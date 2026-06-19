"""Tests for WeightAdapter API endpoints."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aegis.api.app import app
from aegis.models.base import Base
from aegis.models.factor_weight import FactorWeight


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    """Use file-based SQLite so _get_session() sees the same tables."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    # Pre-populate with a factor
    with Session(engine) as s:
        fw = FactorWeight(factor_name="trend_phase", weight=1.0)
        s.add(fw)
        s.commit()

    # Patch settings so _get_session() uses the same file DB
    monkeypatch.setattr(
        "aegis.api.routes.weights.settings.DATABASE_URL", db_url
    )
    yield


class TestGetWeights:
    def test_returns_weights(self, client):
        response = client.get("/api/v1/memory/weights")
        assert response.status_code == 200
        data = response.json()
        assert "factors" in data
        assert "observation_period_active" in data


class TestGetWeightHistory:
    def test_returns_history(self, client):
        response = client.get("/api/v1/memory/weights/history")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestManualOverride:
    """AC-9: manual override API."""

    def test_override_weight(self, client):
        response = client.post(
            "/api/v1/memory/weights/trend_phase/override",
            json={"weight": 1.5, "reason": "manual adjustment"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["factor"] == "trend_phase"
        assert data["new_weight"] == 1.5
        assert data["changed_by"] == "manual"

    def test_override_clamped(self, client):
        """Weight outside [0.2, 3.0] should be rejected by Pydantic validation."""
        response = client.post(
            "/api/v1/memory/weights/trend_phase/override",
            json={"weight": 5.0, "reason": "too high"},
        )
        assert response.status_code == 422  # Validation error
