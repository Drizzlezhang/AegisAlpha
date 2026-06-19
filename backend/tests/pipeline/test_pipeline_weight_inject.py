"""Tests for Pipeline weight snapshot injection."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aegis.models.base import Base
from aegis.models.factor_weight import FactorWeight


class TestInjectWeightSnapshot:
    """AC-8: Pipeline starts → weight_snapshot non-empty with 6 factors."""

    def test_inject_returns_weights(self, monkeypatch):
        """_inject_weight_snapshot should return factor weights from DB."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as s:
            for name in ["trend_phase", "support_resistance", "smart_money", "fund_flow", "options_iv", "debate_consensus"]:
                s.add(FactorWeight(factor_name=name, weight=1.0))
            s.commit()

        # Patch settings to use in-memory DB
        monkeypatch.setattr(
            "aegis.pipeline.runner.settings.DATABASE_URL",
            "sqlite:///:memory:",
        )
        # Also need to patch the engine creation inside _inject_weight_snapshot
        # Since it creates its own engine, we need to ensure it uses the same in-memory DB
        # This is tricky with in-memory SQLite. Let's use a file-based temp DB instead.
        import tempfile
        import os

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test.db")
        db_url = f"sqlite:///{db_path}"

        # Recreate tables in file-based DB
        file_engine = create_engine(db_url)
        Base.metadata.create_all(file_engine)
        with Session(file_engine) as s:
            for name in ["trend_phase", "support_resistance", "smart_money", "fund_flow", "options_iv", "debate_consensus"]:
                s.add(FactorWeight(factor_name=name, weight=1.0))
            s.commit()

        monkeypatch.setattr(
            "aegis.pipeline.runner.settings.DATABASE_URL",
            db_url,
        )

        from aegis.pipeline.runner import _inject_weight_snapshot

        snapshot = _inject_weight_snapshot()
        assert len(snapshot) == 6
        for name in ["trend_phase", "support_resistance", "smart_money", "fund_flow", "options_iv", "debate_consensus"]:
            assert name in snapshot
            assert snapshot[name]["weight"] == 1.0

    def test_inject_empty_db_returns_empty(self, monkeypatch):
        """Empty DB → empty dict, no exception."""
        import tempfile
        import os

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test_empty.db")
        db_url = f"sqlite:///{db_path}"

        file_engine = create_engine(db_url)
        Base.metadata.create_all(file_engine)

        monkeypatch.setattr(
            "aegis.pipeline.runner.settings.DATABASE_URL",
            db_url,
        )

        from aegis.pipeline.runner import _inject_weight_snapshot

        snapshot = _inject_weight_snapshot()
        assert snapshot == {}
