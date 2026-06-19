"""Tests for WeightStore CRUD operations."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from aegis.memory.weight_store import WeightStore
from aegis.models.base import Base
from aegis.models.factor_weight import FactorWeight


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def store():
    return WeightStore()


class TestGetWeight:
    def test_not_found_returns_default(self, session, store):
        assert store.get_weight(session, "nonexistent") == 1.0

    def test_found_returns_weight(self, session, store):
        fw = FactorWeight(factor_name="trend_phase", weight=1.5)
        session.add(fw)
        session.commit()
        assert store.get_weight(session, "trend_phase") == 1.5


class TestGetAllWeights:
    def test_empty(self, session, store):
        assert store.get_all_weights(session) == {}

    def test_multiple_factors(self, session, store):
        session.add_all([
            FactorWeight(factor_name="trend_phase", weight=1.0),
            FactorWeight(factor_name="smart_money", weight=0.8),
        ])
        session.commit()
        result = store.get_all_weights(session)
        assert len(result) == 2
        assert result["trend_phase"]["weight"] == 1.0
        assert result["smart_money"]["weight"] == 0.8


class TestUpdateWeight:
    def test_create_new(self, session, store):
        store.update_weight(session, "trend_phase", 1.5, sample_count=10)
        fw = session.execute(
            select(FactorWeight).where(FactorWeight.factor_name == "trend_phase")
        ).scalar_one()
        assert fw.weight == 1.5
        assert fw.previous_weight is None
        assert fw.sample_count == 10

    def test_update_existing(self, session, store):
        fw = FactorWeight(factor_name="trend_phase", weight=1.0)
        session.add(fw)
        session.commit()

        store.update_weight(session, "trend_phase", 1.2, sample_count=50)
        fw_after = session.execute(
            select(FactorWeight).where(FactorWeight.factor_name == "trend_phase")
        ).scalar_one()
        assert fw_after.weight == 1.2
        assert fw_after.previous_weight == 1.0
        assert fw_after.sample_count == 50


class TestGetWeightHistory:
    """AC-10: weight history queryable."""

    def test_empty(self, session, store):
        assert store.get_weight_history(session) == []

    def test_returns_current_state(self, session, store):
        session.add_all([
            FactorWeight(factor_name="trend_phase", weight=1.2, previous_weight=1.0, sample_count=50),
            FactorWeight(factor_name="smart_money", weight=0.8, previous_weight=1.0, sample_count=30),
        ])
        session.commit()
        history = store.get_weight_history(session)
        assert len(history) == 2

    def test_filter_by_factor(self, session, store):
        session.add_all([
            FactorWeight(factor_name="trend_phase", weight=1.2),
            FactorWeight(factor_name="smart_money", weight=0.8),
        ])
        session.commit()
        history = store.get_weight_history(session, factor_name="trend_phase")
        assert len(history) == 1
        assert history[0]["factor_name"] == "trend_phase"


class TestInitializeFromConfig:
    """AC-11: initial weights loaded from YAML."""

    def test_empty_table_loads_from_config(self, session, store):
        store.initialize_from_config(session)
        result = store.get_all_weights(session)
        assert len(result) == 6
        for name in ["trend_phase", "support_resistance", "smart_money", "fund_flow", "options_iv", "debate_consensus"]:
            assert name in result
            assert result[name]["weight"] == 1.0

    def test_non_empty_table_skips(self, session, store):
        fw = FactorWeight(factor_name="custom", weight=2.0)
        session.add(fw)
        session.commit()

        store.initialize_from_config(session)
        result = store.get_all_weights(session)
        # Should still only have the custom entry
        assert len(result) == 1
        assert "custom" in result


class TestIsObservationPeriodActive:
    def test_empty_table(self, session, store):
        assert store.is_observation_period_active(session) is False

    def test_active(self, session, store):
        fw = FactorWeight(factor_name="trend_phase", weight=1.0, observation_period_active=True)
        session.add(fw)
        session.commit()
        assert store.is_observation_period_active(session) is True

    def test_inactive(self, session, store):
        fw = FactorWeight(factor_name="trend_phase", weight=1.0, observation_period_active=False)
        session.add(fw)
        session.commit()
        assert store.is_observation_period_active(session) is False
