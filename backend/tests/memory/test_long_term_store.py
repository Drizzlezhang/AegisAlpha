"""Tests for LongTermStore CRUD + compression operations."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aegis.memory.long_term_store import LongTermStore
from aegis.models.base import Base


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def store(session):
    return LongTermStore(lambda: session)


class TestInsert:
    def test_insert_returns_id(self, store):
        rid = store.insert({
            "ticker": "QQQ",
            "data_type": "debate",
            "content": {"direction": "bullish"},
            "original_date": datetime.now(UTC),
        })
        assert rid > 0

    def test_insert_with_optional_fields(self, store):
        rid = store.insert({
            "ticker": "QQQ",
            "data_type": "debate",
            "content": {"direction": "bullish"},
            "original_date": datetime.now(UTC),
            "summary": "test summary",
            "is_compressed": True,
            "embedding_id": "emb_123",
        })
        assert rid > 0


class TestQuery:
    def test_empty_table(self, store):
        assert store.query() == []

    def test_filter_by_ticker(self, store, session):
        from aegis.models.long_term_memory import LongTermMemory
        session.add_all([
            LongTermMemory(ticker="QQQ", data_type="debate", content={},
                          original_date=datetime.now(UTC)),
            LongTermMemory(ticker="SPY", data_type="debate", content={},
                          original_date=datetime.now(UTC)),
        ])
        session.commit()
        results = store.query(ticker="QQQ")
        assert len(results) == 1
        assert results[0]["ticker"] == "QQQ"

    def test_filter_by_data_type(self, store, session):
        from aegis.models.long_term_memory import LongTermMemory
        session.add_all([
            LongTermMemory(ticker="QQQ", data_type="debate", content={},
                          original_date=datetime.now(UTC)),
            LongTermMemory(ticker="QQQ", data_type="recommendation", content={},
                          original_date=datetime.now(UTC)),
        ])
        session.commit()
        results = store.query(data_type="debate")
        assert len(results) == 1

    def test_filter_by_date_range(self, store, session):
        from aegis.models.long_term_memory import LongTermMemory
        d1 = datetime(2026, 1, 1, tzinfo=UTC)
        d2 = datetime(2026, 6, 1, tzinfo=UTC)
        d3 = datetime(2026, 12, 1, tzinfo=UTC)
        session.add_all([
            LongTermMemory(ticker="QQQ", data_type="debate", content={}, original_date=d1),
            LongTermMemory(ticker="QQQ", data_type="debate", content={}, original_date=d2),
            LongTermMemory(ticker="QQQ", data_type="debate", content={}, original_date=d3),
        ])
        session.commit()
        results = store.query(date_from=d1, date_to=d2)
        assert len(results) == 2

    def test_filter_by_is_compressed(self, store, session):
        from aegis.models.long_term_memory import LongTermMemory
        session.add_all([
            LongTermMemory(ticker="QQQ", data_type="debate", content={},
                          original_date=datetime.now(UTC), is_compressed=True),
            LongTermMemory(ticker="QQQ", data_type="debate", content={},
                          original_date=datetime.now(UTC), is_compressed=False),
        ])
        session.commit()
        assert len(store.query(is_compressed=True)) == 1
        assert len(store.query(is_compressed=False)) == 1


class TestMarkCompressed:
    def test_empty_ids(self, store):
        assert store.mark_compressed([], "summary") == 0

    def test_marks_records(self, store, session):
        from aegis.models.long_term_memory import LongTermMemory
        row = LongTermMemory(
            ticker="QQQ", data_type="debate", content={},
            original_date=datetime.now(UTC), is_compressed=False,
        )
        session.add(row)
        session.commit()

        count = store.mark_compressed([row.id], "compressed summary", "emb_123")
        assert count == 1

        results = store.query(is_compressed=True)
        assert len(results) == 1
        assert results[0]["summary"] == "compressed summary"
        assert results[0]["embedding_id"] == "emb_123"


class TestGetUncompressedBefore:
    def test_empty(self, store):
        cutoff = datetime.now(UTC) - timedelta(days=30)
        assert store.get_uncompressed_before("debate", cutoff) == []

    def test_returns_oldest_first(self, store, session):
        from aegis.models.long_term_memory import LongTermMemory
        d1 = datetime(2026, 1, 1, tzinfo=UTC)
        d2 = datetime(2026, 2, 1, tzinfo=UTC)
        d3 = datetime(2026, 6, 15, tzinfo=UTC)
        session.add_all([
            LongTermMemory(ticker="QQQ", data_type="debate", content={},
                          original_date=d1, is_compressed=False),
            LongTermMemory(ticker="QQQ", data_type="debate", content={},
                          original_date=d2, is_compressed=False),
            LongTermMemory(ticker="QQQ", data_type="debate", content={},
                          original_date=d3, is_compressed=False),
        ])
        session.commit()

        cutoff = datetime(2026, 3, 1, tzinfo=UTC)
        results = store.get_uncompressed_before("debate", cutoff)
        assert len(results) == 2
        # SQLite stores naive datetimes, strip tz for comparison
        assert results[0]["original_date"].replace("+00:00", "") == d1.isoformat().replace("+00:00", "")
        assert results[1]["original_date"].replace("+00:00", "") == d2.isoformat().replace("+00:00", "")

    def test_excludes_compressed(self, store, session):
        from aegis.models.long_term_memory import LongTermMemory
        d1 = datetime(2026, 1, 1, tzinfo=UTC)
        session.add_all([
            LongTermMemory(ticker="QQQ", data_type="debate", content={},
                          original_date=d1, is_compressed=True),
            LongTermMemory(ticker="QQQ", data_type="debate", content={},
                          original_date=d1, is_compressed=False),
        ])
        session.commit()

        cutoff = datetime(2026, 3, 1, tzinfo=UTC)
        results = store.get_uncompressed_before("debate", cutoff)
        assert len(results) == 1
        assert results[0]["is_compressed"] is False


class TestSummarize:
    def test_empty(self, store):
        result = store.summarize(None, ("2026-01-01", "2026-06-01"))
        assert result["count"] == 0
        assert result["data_types"] == []

    def test_with_data(self, store, session):
        from aegis.models.long_term_memory import LongTermMemory
        session.add_all([
            LongTermMemory(ticker="QQQ", data_type="debate", content={},
                          original_date=datetime(2026, 3, 1, tzinfo=UTC)),
            LongTermMemory(ticker="QQQ", data_type="recommendation", content={},
                          original_date=datetime(2026, 4, 1, tzinfo=UTC)),
        ])
        session.commit()
        result = store.summarize("QQQ", ("2026-01-01", "2026-06-01"))
        assert result["count"] == 2
        assert "debate" in result["data_types"]
        assert "recommendation" in result["data_types"]
