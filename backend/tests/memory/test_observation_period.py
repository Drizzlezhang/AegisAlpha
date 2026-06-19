"""Tests for ObservationPeriodManager."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aegis.memory.observation_period import ObservationPeriodManager
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
def manager(session):
    ws = WeightStore()
    ts = ThesisStore()
    wa = WeightAdapter(ws, ts)
    return ObservationPeriodManager(ws, ts, wa)


class TestObservationPeriod:
    """AC-3: observation period 30 days — no weight change."""

    def test_no_cards_in_period(self, session, manager):
        """No cards → in observation period."""
        assert manager.is_in_observation_period(session) is True

    def test_recent_card_in_period(self, session, manager):
        """Card created 10 days ago → still in period."""
        card = ThesisCard(
            ticker="QQQ",
            direction="bull",
            entry_mode="active_left",
            entry_date=datetime.now(UTC) - timedelta(days=10),
            entry_price=400.0,
            created_at=datetime.now(UTC) - timedelta(days=10),
        )
        session.add(card)
        session.commit()
        assert manager.is_in_observation_period(session) is True

    def test_old_card_out_of_period(self, session, manager):
        """Card created 31 days ago → out of period."""
        card = ThesisCard(
            ticker="QQQ",
            direction="bull",
            entry_mode="active_left",
            entry_date=datetime.now(UTC) - timedelta(days=31),
            entry_price=400.0,
            created_at=datetime.now(UTC) - timedelta(days=31),
        )
        session.add(card)
        session.commit()
        assert manager.is_in_observation_period(session) is False


class TestCheckAndTransition:
    """AC-4: observation period ends → backfill triggered."""

    def test_no_transition_when_active(self, session, manager):
        """Observation period still active → no transition."""
        # Create a factor with observation_period_active=True
        fw = FactorWeight(factor_name="trend_phase", weight=1.0)
        session.add(fw)
        session.commit()

        # No cards → in period
        result = manager.check_and_transition(session)
        assert result is False

    def test_transition_when_period_ends(self, session, manager):
        """Observation period ended → transition triggered."""
        # Create a factor with observation_period_active=True
        fw = FactorWeight(factor_name="trend_phase", weight=1.0)
        session.add(fw)
        session.commit()

        # Create old card (31 days ago)
        card = ThesisCard(
            ticker="QQQ",
            direction="bull",
            entry_mode="active_left",
            entry_date=datetime.now(UTC) - timedelta(days=31),
            entry_price=400.0,
            created_at=datetime.now(UTC) - timedelta(days=31),
        )
        session.add(card)
        session.commit()

        result = manager.check_and_transition(session)
        assert result is True

        # Factor should now be marked as observation_period_active=False
        from sqlalchemy import select
        fw_after = session.execute(
            select(FactorWeight).where(FactorWeight.factor_name == "trend_phase")
        ).scalar_one()
        assert fw_after.observation_period_active is False
