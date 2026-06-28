"""Tests for KOLStore — CRUD operations on kol_sources and kol_calls."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from aegis.models.base import Base
from aegis.storage.kol_store import KOLStore


@pytest.fixture
async def store() -> KOLStore:
    """Create an in-memory SQLite KOLStore for testing."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    def session_factory() -> AsyncSession:
        return AsyncSession(engine)

    s = KOLStore(session_factory)
    yield s
    await engine.dispose()


def _source_data(**overrides: Any) -> dict[str, Any]:
    base = {
        "name": "Test KOL",
        "platform": "x",
        "handle": "testuser",
    }
    base.update(overrides)
    return base


def _call_data(source_id: int, **overrides: Any) -> dict[str, Any]:
    base = {
        "kol_source_id": source_id,
        "ticker": "QQQ",
        "direction": "bullish",
        "call_date": datetime.now(timezone.utc),
        "call_price": 450.0,
    }
    base.update(overrides)
    return base


class TestKOLStoreSources:
    @pytest.mark.asyncio
    async def test_create_and_get_source(self, store: KOLStore) -> None:
        """Should create a KOL source and retrieve it by ID."""
        source_id = await store.create_source(_source_data())
        assert source_id > 0

        source = await store.get_source(source_id)
        assert source is not None
        assert source.name == "Test KOL"
        assert source.platform == "x"
        assert source.handle == "testuser"
        assert source.reliability_score == 0.5
        assert source.enabled is True

    @pytest.mark.asyncio
    async def test_get_source_not_found(self, store: KOLStore) -> None:
        """Should return None for non-existent source."""
        source = await store.get_source(999)
        assert source is None

    @pytest.mark.asyncio
    async def test_list_sources_enabled_only(self, store: KOLStore) -> None:
        """Should list only enabled sources by default."""
        await store.create_source(_source_data(name="A", handle="a"))
        await store.create_source(_source_data(name="B", handle="b"))
        sid = await store.create_source(_source_data(name="C", handle="c"))
        await store.update_source(sid, {"enabled": False})

        sources = await store.list_sources(enabled_only=True)
        assert len(sources) == 2

    @pytest.mark.asyncio
    async def test_list_sources_all(self, store: KOLStore) -> None:
        """Should list all sources when enabled_only=False."""
        await store.create_source(_source_data(name="A", handle="a"))
        sid = await store.create_source(_source_data(name="B", handle="b"))
        await store.update_source(sid, {"enabled": False})

        sources = await store.list_sources(enabled_only=False)
        assert len(sources) == 2

    @pytest.mark.asyncio
    async def test_update_source(self, store: KOLStore) -> None:
        """Should update source fields."""
        source_id = await store.create_source(_source_data())
        await store.update_source(source_id, {"reliability_score": 0.8, "enabled": False})

        source = await store.get_source(source_id)
        assert source is not None
        assert source.reliability_score == 0.8
        assert source.enabled is False


class TestKOLStoreCalls:
    @pytest.mark.asyncio
    async def test_record_call(self, store: KOLStore) -> None:
        """Should record a KOL call."""
        source_id = await store.create_source(_source_data())
        call_id = await store.record_call(_call_data(source_id))
        assert call_id > 0

    @pytest.mark.asyncio
    async def test_record_call_string_date(self, store: KOLStore) -> None:
        """Should handle string call_date."""
        source_id = await store.create_source(_source_data())
        call_id = await store.record_call(
            _call_data(source_id, call_date="2026-06-20T10:00:00+00:00")
        )
        assert call_id > 0

    @pytest.mark.asyncio
    async def test_get_pending_attribution(self, store: KOLStore) -> None:
        """Should return pending calls older than N days."""
        source_id = await store.create_source(_source_data())

        # Old pending call
        old_date = datetime.now(timezone.utc) - timedelta(days=35)
        await store.record_call(
            _call_data(source_id, call_date=old_date)
        )

        # Recent pending call (should not be returned for 30d)
        recent_date = datetime.now(timezone.utc) - timedelta(days=10)
        await store.record_call(
            _call_data(source_id, call_date=recent_date)
        )

        pending = await store.get_pending_attribution(days_ago=30)
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_update_attribution(self, store: KOLStore) -> None:
        """Should update attribution status and P&L."""
        source_id = await store.create_source(_source_data())
        call_id = await store.record_call(_call_data(source_id))

        await store.update_attribution(call_id, "validated", 0.15)

        # Verify via stats
        stats = await store.get_attribution_stats(source_id)
        assert stats["validated"] == 1
        assert stats["pending"] == 0

    @pytest.mark.asyncio
    async def test_update_pnl_60d(self, store: KOLStore) -> None:
        """Should update 60d P&L."""
        source_id = await store.create_source(_source_data())
        old_date = datetime.now(timezone.utc) - timedelta(days=65)
        call_id = await store.record_call(
            _call_data(source_id, call_date=old_date)
        )
        await store.update_attribution(call_id, "validated", 0.10)

        await store.update_pnl_60d(call_id, 0.20)

        # Verify via 60d query
        needs_60d = await store.get_calls_needing_60d_update()
        assert len(needs_60d) == 0  # pnl_60d is now set

    @pytest.mark.asyncio
    async def test_get_calls_needing_60d_update(self, store: KOLStore) -> None:
        """Should return calls with 30d attribution but missing 60d P&L."""
        source_id = await store.create_source(_source_data())
        old_date = datetime.now(timezone.utc) - timedelta(days=65)
        call_id = await store.record_call(
            _call_data(source_id, call_date=old_date)
        )
        await store.update_attribution(call_id, "validated", 0.10)

        needs_60d = await store.get_calls_needing_60d_update()
        assert len(needs_60d) == 1

    @pytest.mark.asyncio
    async def test_get_calls_by_ticker(self, store: KOLStore) -> None:
        """Should return calls for a specific ticker."""
        source_id = await store.create_source(_source_data())
        await store.record_call(_call_data(source_id, ticker="QQQ"))
        await store.record_call(_call_data(source_id, ticker="SPY"))

        qqq_calls = await store.get_calls_by_ticker("QQQ")
        assert len(qqq_calls) == 1
        assert qqq_calls[0].ticker == "QQQ"

    @pytest.mark.asyncio
    async def test_get_attribution_stats(self, store: KOLStore) -> None:
        """Should return correct attribution statistics."""
        source_id = await store.create_source(_source_data())
        await store.record_call(_call_data(source_id))
        await store.record_call(_call_data(source_id))

        stats = await store.get_attribution_stats()
        assert stats["total"] == 2
        assert stats["pending"] == 2
        assert stats["validated"] == 0
        assert stats["invalidated"] == 0
