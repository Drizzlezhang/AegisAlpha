"""Tests for ThesisCard SQLAlchemy model."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from aegis.models.base import Base
from aegis.models.thesis import ThesisCard


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_create_thesis_card(session: Session):
    """Should create and persist a ThesisCard record."""
    card = ThesisCard(
        ticker="QQQ",
        direction="long",
        entry_mode="active_left",
        entry_date=datetime(2026, 1, 15, tzinfo=UTC),
        entry_price=480.0,
        target_price=550.0,
        stop_price=450.0,
        key_assumptions=["trend_up", "support_holds"],
        thesis_valid_status="valid",
        factor_snapshot={"trend_phase": 1.0, "smart_money": 0.8},
    )
    session.add(card)
    session.commit()

    result = session.execute(
        select(ThesisCard).where(ThesisCard.ticker == "QQQ")
    ).scalar_one()
    assert result.ticker == "QQQ"
    assert result.direction == "long"
    assert result.entry_mode == "active_left"
    assert result.entry_price == 480.0
    assert result.target_price == 550.0
    assert result.stop_price == 450.0
    assert result.key_assumptions == ["trend_up", "support_holds"]
    assert result.thesis_valid_status == "valid"
    assert result.re_entry_flagged is False
    assert result.factor_snapshot["trend_phase"] == 1.0


def test_thesis_card_defaults(session: Session):
    """Default values should be set correctly."""
    card = ThesisCard(
        ticker="SPY",
        direction="short_put",
        entry_mode="passive",
        entry_date=datetime(2026, 3, 1, tzinfo=UTC),
        entry_price=520.0,
    )
    session.add(card)
    session.commit()

    result = session.execute(select(ThesisCard)).scalar_one()
    assert result.key_assumptions == []
    assert result.thesis_valid_status == "valid"
    assert result.re_entry_flagged is False
    assert result.factor_snapshot == {}
    assert result.close_date is None
    assert result.close_price is None
    assert result.actual_pnl_pct is None
    assert result.judgment_score is None
    assert result.execution_score is None
    assert result.close_reason is None


def test_thesis_card_close(session: Session):
    """Should support closing a thesis with scores."""
    card = ThesisCard(
        ticker="QQQ",
        direction="long",
        entry_mode="active_left",
        entry_date=datetime(2026, 1, 15, tzinfo=UTC),
        entry_price=480.0,
    )
    session.add(card)
    session.commit()

    card.close_date = datetime(2026, 6, 1, tzinfo=UTC)
    card.close_price = 530.0
    card.actual_pnl_pct = 10.42
    card.judgment_score = 4
    card.execution_score = 5
    card.close_reason = "target_reached"
    session.commit()

    result = session.execute(select(ThesisCard)).scalar_one()
    assert result.close_price == 530.0
    assert result.actual_pnl_pct == 10.42
    assert result.judgment_score == 4
    assert result.execution_score == 5
    assert result.close_reason == "target_reached"


def test_thesis_card_query_by_ticker(session: Session):
    """Should filter by ticker."""
    session.add_all([
        ThesisCard(
            ticker="QQQ", direction="long", entry_mode="active_left",
            entry_date=datetime(2026, 1, 1, tzinfo=UTC), entry_price=400.0,
        ),
        ThesisCard(
            ticker="SPY", direction="long", entry_mode="passive",
            entry_date=datetime(2026, 2, 1, tzinfo=UTC), entry_price=500.0,
        ),
    ])
    session.commit()

    results = session.execute(
        select(ThesisCard).where(ThesisCard.ticker == "QQQ")
    ).all()
    assert len(results) == 1
