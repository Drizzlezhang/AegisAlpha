"""Tests for LongTermMemory SQLAlchemy model."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from aegis.models.base import Base
from aegis.models.long_term_memory import LongTermMemory


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_create_long_term_memory(session: Session):
    """Should create and persist a LongTermMemory record."""
    mem = LongTermMemory(
        ticker="QQQ",
        data_type="debate",
        content={"bull_score": 75, "bear_score": 60, "consensus": "bullish"},
        summary="Bullish consensus with moderate confidence",
        original_date=datetime(2026, 6, 15, tzinfo=UTC),
        embedding_id="emb-abc123",
    )
    session.add(mem)
    session.commit()

    result = session.execute(
        select(LongTermMemory).where(LongTermMemory.ticker == "QQQ")
    ).scalar_one()
    assert result.ticker == "QQQ"
    assert result.data_type == "debate"
    assert result.content["bull_score"] == 75
    assert result.summary == "Bullish consensus with moderate confidence"
    assert result.embedding_id == "emb-abc123"
    assert result.is_compressed is False
    assert result.compressed_at is None


def test_long_term_memory_defaults(session: Session):
    """Default values should be set correctly."""
    mem = LongTermMemory(
        data_type="recommendation",
        content={"action": "buy"},
        original_date=datetime(2026, 6, 1, tzinfo=UTC),
    )
    session.add(mem)
    session.commit()

    result = session.execute(select(LongTermMemory)).scalar_one()
    assert result.ticker is None
    assert result.summary is None
    assert result.is_compressed is False
    assert result.compressed_at is None
    assert result.embedding_id is None


def test_long_term_memory_compression(session: Session):
    """Should support compression with summary."""
    mem = LongTermMemory(
        ticker="QQQ",
        data_type="debate",
        content={"bull_score": 75, "bear_score": 60},
        original_date=datetime(2026, 3, 1, tzinfo=UTC),
    )
    session.add(mem)
    session.commit()

    mem.summary = "Bullish consensus"
    mem.is_compressed = True
    mem.compressed_at = datetime(2026, 6, 15, tzinfo=UTC)
    session.commit()

    result = session.execute(select(LongTermMemory)).scalar_one()
    assert result.is_compressed is True
    assert result.summary == "Bullish consensus"
    assert result.compressed_at is not None


def test_long_term_memory_query_by_data_type(session: Session):
    """Should filter by data_type."""
    session.add_all([
        LongTermMemory(
            data_type="debate", content={},
            original_date=datetime(2026, 6, 1, tzinfo=UTC),
        ),
        LongTermMemory(
            data_type="recommendation", content={},
            original_date=datetime(2026, 6, 1, tzinfo=UTC),
        ),
    ])
    session.commit()

    results = session.execute(
        select(LongTermMemory).where(LongTermMemory.data_type == "debate")
    ).all()
    assert len(results) == 1
