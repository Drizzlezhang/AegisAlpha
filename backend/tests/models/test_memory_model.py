"""Tests for ShortTermMemory SQLAlchemy model."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from aegis.models.base import Base
from aegis.models.memory import ShortTermMemory


@pytest.fixture
def session() -> Session:
    """In-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_create_short_term_memory(session: Session):
    """Should create and persist a ShortTermMemory record."""
    now = datetime.now(UTC)
    expires = now + timedelta(days=14)
    mem = ShortTermMemory(
        ticker="QQQ",
        data_type="trend",
        content={"direction": "bullish", "score": 75},
        expires_at=expires,
        pipeline_id="pipe-001",
    )
    session.add(mem)
    session.commit()

    result = session.execute(
        select(ShortTermMemory).where(ShortTermMemory.ticker == "QQQ")
    ).scalar_one()
    assert result.ticker == "QQQ"
    assert result.data_type == "trend"
    assert result.content["direction"] == "bullish"
    assert result.pipeline_id == "pipe-001"


def test_query_by_ticker(session: Session):
    """Should filter by ticker."""
    now = datetime.now(UTC)
    expires = now + timedelta(days=14)
    session.add_all([
        ShortTermMemory(ticker="QQQ", data_type="trend", content={}, expires_at=expires),
        ShortTermMemory(ticker="SPY", data_type="trend", content={}, expires_at=expires),
    ])
    session.commit()

    results = session.execute(
        select(ShortTermMemory).where(ShortTermMemory.ticker == "QQQ")
    ).all()
    assert len(results) == 1


def test_ttl_expiry_filter(session: Session):
    """Should filter out expired records."""
    now = datetime.now(UTC)
    expired = now - timedelta(days=1)
    valid = now + timedelta(days=14)

    session.add_all([
        ShortTermMemory(ticker="QQQ", data_type="trend", content={}, expires_at=expired),
        ShortTermMemory(ticker="QQQ", data_type="debate", content={}, expires_at=valid),
    ])
    session.commit()

    results = session.execute(
        select(ShortTermMemory).where(ShortTermMemory.expires_at > now)
    ).all()
    assert len(results) == 1
    assert results[0][0].data_type == "debate"


def test_default_values(session: Session):
    """Default values should be set correctly."""
    now = datetime.now(UTC)
    expires = now + timedelta(days=14)
    mem = ShortTermMemory(expires_at=expires)
    session.add(mem)
    session.commit()

    result = session.execute(select(ShortTermMemory)).scalar_one()
    assert result.ticker == ""
    assert result.data_type == ""
    assert result.content == {}
    assert result.pipeline_id == ""
