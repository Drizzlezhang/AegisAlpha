"""Tests for WeightAdapter edge cases: insufficient samples, empty cards."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aegis.memory.thesis_store import ThesisStore
from aegis.memory.weight_adapter import WeightAdapter
from aegis.memory.weight_store import WeightStore
from aegis.models.base import Base
from aegis.models.factor_weight import FactorWeight
from aegis.models.thesis import ThesisCard


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def adapter():
    return WeightAdapter(WeightStore(), ThesisStore())


class TestInsufficientSamples:
    """AC-6: < 5 samples → keep current weight."""

    def test_insufficient_samples_no_update(self, session, adapter):
        # Create a factor with current weight
        fw = FactorWeight(factor_name="trend_phase", weight=1.5)
        session.add(fw)
        session.commit()

        # Create only 3 closed cards with factor_snapshot
        for i in range(3):
            card = ThesisCard(
                ticker="QQQ",
                direction="bull",
                entry_mode="active_left",
                entry_date=datetime(2026, 1, 1),
                entry_price=400.0,
                close_date=datetime(2026, 3, 1),
                close_price=420.0,
                actual_pnl_pct=5.0,
                judgment_score=3,
                execution_score=3,
                factor_snapshot={"trend_phase": 60.0},
            )
            session.add(card)
        session.commit()

        updated = adapter.update_weights(session)
        # trend_phase should NOT be in updated (only 3 samples)
        assert "trend_phase" not in updated

        # Weight should remain unchanged
        ws = WeightStore()
        assert ws.get_weight(session, "trend_phase") == 1.5


class TestEmptyCards:
    """AC-7: empty closed cards → return current weights."""

    def test_empty_cards(self, session, adapter):
        updated = adapter.update_weights(session)
        assert updated == {}

    def test_no_closed_cards(self, session, adapter):
        # Card exists but not closed
        card = ThesisCard(
            ticker="QQQ",
            direction="bull",
            entry_mode="active_left",
            entry_date=datetime(2026, 1, 1),
            entry_price=400.0,
        )
        session.add(card)
        session.commit()

        updated = adapter.update_weights(session)
        assert updated == {}


class TestMissingScores:
    """Cards missing judgment/execution scores are filtered out."""

    def test_missing_judgment_score(self, session, adapter):
        fw = FactorWeight(factor_name="trend_phase", weight=1.0)
        session.add(fw)
        session.commit()

        # Create 5 cards but only 3 have judgment_score
        for i in range(5):
            card = ThesisCard(
                ticker="QQQ",
                direction="bull",
                entry_mode="active_left",
                entry_date=datetime(2026, 1, 1),
                entry_price=400.0,
                close_date=datetime(2026, 3, 1),
                close_price=420.0,
                actual_pnl_pct=5.0,
                judgment_score=3 if i < 3 else None,
                execution_score=3,
                factor_snapshot={"trend_phase": 60.0},
            )
            session.add(card)
        session.commit()

        updated = adapter.update_weights(session)
        # Only 3 valid samples → insufficient
        assert "trend_phase" not in updated
