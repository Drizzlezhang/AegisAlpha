"""Tests for ShortTermStore CRUD + TTL operations."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aegis.memory.short_term_store import ShortTermStore
from aegis.models.base import Base


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def store(session):
    return ShortTermStore(lambda: session)


class TestInsert:
    def test_insert_returns_id(self, store):
        rid = store.insert({
            "ticker": "QQQ",
            "data_type": "debate",
            "content": {"direction": "bullish"},
            "pipeline_id": "abc123",
        })
        assert rid > 0

    def test_insert_sets_expires_at(self, store, session):
        store.insert({
            "ticker": "QQQ",
            "data_type": "test",
            "content": {},
            "pipeline_id": "p1",
        }, ttl_days=7)
        from aegis.models.memory import ShortTermMemory
        from sqlalchemy import select
        row = session.execute(select(ShortTermMemory)).scalar_one()
        expected = datetime.now(UTC) + timedelta(days=7)
        # SQLite stores naive datetimes, compare as UTC
        actual = row.expires_at.replace(tzinfo=UTC)
        assert abs((actual - expected).total_seconds()) < 5


class TestQuery:
    def test_empty_table(self, store):
        assert store.query() == []

    def test_filters_expired(self, store, session):
        from aegis.models.memory import ShortTermMemory
        # Insert expired record
        expired = ShortTermMemory(
            ticker="QQQ",
            data_type="old",
            content={},
            pipeline_id="p1",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        session.add(expired)
        session.commit()
        assert store.query() == []

    def test_returns_unexpired(self, store, session):
        from aegis.models.memory import ShortTermMemory
        row = ShortTermMemory(
            ticker="QQQ",
            data_type="debate",
            content={"direction": "bullish"},
            pipeline_id="p1",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        session.add(row)
        session.commit()
        results = store.query()
        assert len(results) == 1
        assert results[0]["ticker"] == "QQQ"
        assert results[0]["data_type"] == "debate"

    def test_filter_by_ticker(self, store, session):
        from aegis.models.memory import ShortTermMemory
        session.add_all([
            ShortTermMemory(ticker="QQQ", data_type="a", content={}, pipeline_id="p1",
                          expires_at=datetime.now(UTC) + timedelta(days=7)),
            ShortTermMemory(ticker="SPY", data_type="a", content={}, pipeline_id="p2",
                          expires_at=datetime.now(UTC) + timedelta(days=7)),
        ])
        session.commit()
        results = store.query(ticker="QQQ")
        assert len(results) == 1
        assert results[0]["ticker"] == "QQQ"

    def test_filter_by_data_type(self, store, session):
        from aegis.models.memory import ShortTermMemory
        session.add_all([
            ShortTermMemory(ticker="QQQ", data_type="debate", content={}, pipeline_id="p1",
                          expires_at=datetime.now(UTC) + timedelta(days=7)),
            ShortTermMemory(ticker="QQQ", data_type="recommendation", content={}, pipeline_id="p2",
                          expires_at=datetime.now(UTC) + timedelta(days=7)),
        ])
        session.commit()
        results = store.query(data_type="debate")
        assert len(results) == 1
        assert results[0]["data_type"] == "debate"

    def test_respects_limit(self, store, session):
        from aegis.models.memory import ShortTermMemory
        for i in range(5):
            session.add(ShortTermMemory(
                ticker="QQQ", data_type=f"type_{i}", content={}, pipeline_id=f"p{i}",
                expires_at=datetime.now(UTC) + timedelta(days=7),
            ))
        session.commit()
        results = store.query(limit=3)
        assert len(results) == 3


class TestCleanupExpired:
    def test_no_expired(self, store):
        assert store.cleanup_expired() == 0

    def test_deletes_expired(self, store, session):
        from aegis.models.memory import ShortTermMemory
        session.add_all([
            ShortTermMemory(ticker="QQQ", data_type="a", content={}, pipeline_id="p1",
                          expires_at=datetime.now(UTC) - timedelta(days=1)),
            ShortTermMemory(ticker="QQQ", data_type="b", content={}, pipeline_id="p2",
                          expires_at=datetime.now(UTC) + timedelta(days=7)),
        ])
        session.commit()
        deleted = store.cleanup_expired()
        assert deleted == 1
        # Verify only unexpired remains
        results = store.query()
        assert len(results) == 1
        assert results[0]["data_type"] == "b"
