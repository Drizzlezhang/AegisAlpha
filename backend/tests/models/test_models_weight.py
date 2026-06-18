"""Tests for FactorWeight SQLAlchemy model."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from aegis.models.base import Base
from aegis.models.factor_weight import FactorWeight


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_create_factor_weight(session: Session):
    """Should create and persist a FactorWeight record."""
    fw = FactorWeight(
        factor_name="trend_phase",
        weight=1.2,
        previous_weight=1.0,
        changed_by="system",
        observation_period_active=False,
        sample_count=50,
    )
    session.add(fw)
    session.commit()

    result = session.execute(
        select(FactorWeight).where(FactorWeight.factor_name == "trend_phase")
    ).scalar_one()
    assert result.factor_name == "trend_phase"
    assert result.weight == 1.2
    assert result.previous_weight == 1.0
    assert result.changed_by == "system"
    assert result.observation_period_active is False
    assert result.sample_count == 50


def test_factor_weight_defaults(session: Session):
    """Default values should be set correctly."""
    fw = FactorWeight(factor_name="smart_money", weight=1.0)
    session.add(fw)
    session.commit()

    result = session.execute(select(FactorWeight)).scalar_one()
    assert result.previous_weight is None
    assert result.changed_by == "system"
    assert result.observation_period_active is True
    assert result.sample_count == 0


def test_factor_weight_update(session: Session):
    """Should support updating weight and tracking previous."""
    fw = FactorWeight(factor_name="fund_flow", weight=1.0)
    session.add(fw)
    session.commit()

    fw.previous_weight = 1.0
    fw.weight = 0.8
    fw.sample_count = 10
    session.commit()

    result = session.execute(select(FactorWeight)).scalar_one()
    assert result.weight == 0.8
    assert result.previous_weight == 1.0
    assert result.sample_count == 10


def test_factor_weight_query_by_name(session: Session):
    """Should filter by factor_name."""
    session.add_all([
        FactorWeight(factor_name="trend_phase", weight=1.0),
        FactorWeight(factor_name="smart_money", weight=0.8),
    ])
    session.commit()

    results = session.execute(
        select(FactorWeight).where(FactorWeight.factor_name == "smart_money")
    ).all()
    assert len(results) == 1
    assert results[0][0].weight == 0.8
