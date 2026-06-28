"""Tests for ThesisStore — CRUD operations on thesis_cards table."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from aegis.models.base import Base
from aegis.storage.thesis_store import ThesisStore


@pytest.fixture
async def store() -> ThesisStore:
    """Create an in-memory SQLite ThesisStore for testing."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    def session_factory() -> AsyncSession:
        return AsyncSession(engine)

    store = ThesisStore(session_factory)
    yield store
    await engine.dispose()


def _card_data(**overrides: Any) -> dict[str, Any]:
    base = {
        "ticker": "QQQ",
        "direction": "long",
        "entry_mode": "active_right",
        "entry_date": datetime.now(timezone.utc),
        "entry_price": 450.0,
        "target_price": 500.0,
        "stop_price": 420.0,
        "key_assumptions": ["QQQ above 200MA", "tech momentum"],
        "thesis_valid_status": "valid",
        "re_entry_flagged": False,
        "factor_snapshot": {"trend_phase": 75},
    }
    base.update(overrides)
    return base


class TestThesisStoreCRUD:
    @pytest.mark.asyncio
    async def test_create_and_get_by_id(self, store: ThesisStore) -> None:
        """Should create a ThesisCard and retrieve it by ID."""
        thesis_id = await store.create(_card_data())
        assert thesis_id > 0

        card = await store.get_by_id(thesis_id)
        assert card is not None
        assert card.ticker == "QQQ"
        assert card.direction == "long"
        assert card.entry_price == 450.0
        assert card.thesis_valid_status == "valid"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, store: ThesisStore) -> None:
        """Should return None for non-existent ID."""
        card = await store.get_by_id(999)
        assert card is None

    @pytest.mark.asyncio
    async def test_get_active(self, store: ThesisStore) -> None:
        """Should return only unclosed ThesisCards."""
        await store.create(_card_data(ticker="QQQ"))
        await store.create(_card_data(ticker="SPY"))

        active = await store.get_active()
        assert len(active) == 2

    @pytest.mark.asyncio
    async def test_get_active_filtered_by_ticker(self, store: ThesisStore) -> None:
        """Should filter active ThesisCards by ticker."""
        await store.create(_card_data(ticker="QQQ"))
        await store.create(_card_data(ticker="SPY"))

        active = await store.get_active(ticker="QQQ")
        assert len(active) == 1
        assert active[0].ticker == "QQQ"

    @pytest.mark.asyncio
    async def test_get_active_excludes_closed(self, store: ThesisStore) -> None:
        """Should exclude closed ThesisCards from active results."""
        thesis_id = await store.create(_card_data())
        await store.close(thesis_id, {
            "close_date": datetime.now(timezone.utc),
            "close_price": 480.0,
            "actual_pnl_pct": 0.0667,
            "judgment_score": 4,
            "execution_score": 3,
            "close_reason": "target_reached",
        })

        active = await store.get_active()
        assert len(active) == 0

    @pytest.mark.asyncio
    async def test_update(self, store: ThesisStore) -> None:
        """Should partially update a ThesisCard."""
        thesis_id = await store.create(_card_data())

        await store.update(thesis_id, {"target_price": 520.0, "stop_price": 440.0})

        card = await store.get_by_id(thesis_id)
        assert card is not None
        assert card.target_price == 520.0
        assert card.stop_price == 440.0

    @pytest.mark.asyncio
    async def test_close(self, store: ThesisStore) -> None:
        """Should close a ThesisCard with all close fields."""
        thesis_id = await store.create(_card_data())

        await store.close(thesis_id, {
            "close_date": datetime.now(timezone.utc),
            "close_price": 480.0,
            "actual_pnl_pct": 0.0667,
            "judgment_score": 4,
            "execution_score": 3,
            "close_reason": "target_reached",
        })

        card = await store.get_by_id(thesis_id)
        assert card is not None
        assert card.close_date is not None
        assert card.close_price == 480.0
        assert card.actual_pnl_pct == pytest.approx(0.0667)
        assert card.judgment_score == 4
        assert card.execution_score == 3
        assert card.close_reason == "target_reached"


class TestThesisStoreQueries:
    @pytest.mark.asyncio
    async def test_get_closed_with_scores(self, store: ThesisStore) -> None:
        """Should return only closed cards with both scores."""
        # Create and close a card
        thesis_id = await store.create(_card_data())
        await store.close(thesis_id, {
            "close_date": datetime.now(timezone.utc),
            "close_price": 480.0,
            "actual_pnl_pct": 0.0667,
            "judgment_score": 4,
            "execution_score": 3,
            "close_reason": "target_reached",
        })

        # Create an active card (should not appear)
        await store.create(_card_data(ticker="SPY"))

        closed = await store.get_closed_with_scores()
        assert len(closed) == 1
        assert closed[0]["ticker"] == "QQQ"
        assert closed[0]["judgment_score"] == 4
        assert closed[0]["execution_score"] == 3

    @pytest.mark.asyncio
    async def test_get_earliest_card(self, store: ThesisStore) -> None:
        """Should return the earliest created ThesisCard."""
        await store.create(_card_data(ticker="QQQ"))
        await store.create(_card_data(ticker="SPY"))

        earliest = await store.get_earliest_card()
        assert earliest is not None
        assert earliest.ticker == "QQQ"

    @pytest.mark.asyncio
    async def test_get_earliest_card_empty(self, store: ThesisStore) -> None:
        """Should return None when no cards exist."""
        earliest = await store.get_earliest_card()
        assert earliest is None

    @pytest.mark.asyncio
    async def test_get_recently_closed(self, store: ThesisStore) -> None:
        """Should return recently closed cards for a ticker."""
        thesis_id = await store.create(_card_data(ticker="QQQ"))
        await store.close(thesis_id, {
            "close_date": datetime.now(timezone.utc) - timedelta(days=10),
            "close_price": 480.0,
            "actual_pnl_pct": 0.0667,
            "judgment_score": 4,
            "execution_score": 3,
            "close_reason": "target_reached",
        })

        recent = await store.get_recently_closed("QQQ", days=30)
        assert len(recent) == 1
        assert recent[0].ticker == "QQQ"

    @pytest.mark.asyncio
    async def test_get_recently_closed_outside_window(self, store: ThesisStore) -> None:
        """Should exclude cards closed outside the days window."""
        thesis_id = await store.create(_card_data(ticker="QQQ"))
        await store.close(thesis_id, {
            "close_date": datetime.now(timezone.utc) - timedelta(days=100),
            "close_price": 480.0,
            "actual_pnl_pct": 0.0667,
            "judgment_score": 4,
            "execution_score": 3,
            "close_reason": "target_reached",
        })

        recent = await store.get_recently_closed("QQQ", days=30)
        assert len(recent) == 0


class TestThesisStoreListAll:
    @pytest.mark.asyncio
    async def test_list_all_no_filters(self, store: ThesisStore) -> None:
        """Should return all cards with default pagination."""
        await store.create(_card_data(ticker="QQQ"))
        await store.create(_card_data(ticker="SPY"))

        cards = await store.list_all()
        assert len(cards) == 2

    @pytest.mark.asyncio
    async def test_list_all_filter_by_status(self, store: ThesisStore) -> None:
        """Should filter by thesis_valid_status."""
        await store.create(_card_data(ticker="QQQ", thesis_valid_status="valid"))
        await store.create(_card_data(ticker="SPY", thesis_valid_status="partial_broken"))

        valid = await store.list_all(filters={"status": "valid"})
        assert len(valid) == 1
        assert valid[0].ticker == "QQQ"

    @pytest.mark.asyncio
    async def test_list_all_filter_closed(self, store: ThesisStore) -> None:
        """Should filter closed cards."""
        await store.create(_card_data(ticker="QQQ"))
        thesis_id = await store.create(_card_data(ticker="SPY"))
        await store.close(thesis_id, {
            "close_date": datetime.now(timezone.utc),
            "close_price": 480.0,
            "actual_pnl_pct": 0.0667,
            "judgment_score": 4,
            "execution_score": 3,
            "close_reason": "target_reached",
        })

        closed = await store.list_all(filters={"status": "closed"})
        assert len(closed) == 1
        assert closed[0].ticker == "SPY"

    @pytest.mark.asyncio
    async def test_list_all_filter_by_ticker(self, store: ThesisStore) -> None:
        """Should filter by ticker."""
        await store.create(_card_data(ticker="QQQ"))
        await store.create(_card_data(ticker="SPY"))

        cards = await store.list_all(filters={"ticker": "QQQ"})
        assert len(cards) == 1
        assert cards[0].ticker == "QQQ"

    @pytest.mark.asyncio
    async def test_list_all_filter_by_direction(self, store: ThesisStore) -> None:
        """Should filter by direction."""
        await store.create(_card_data(ticker="QQQ", direction="long"))
        await store.create(_card_data(ticker="SPY", direction="cc"))

        cards = await store.list_all(filters={"direction": "cc"})
        assert len(cards) == 1
        assert cards[0].direction == "cc"

    @pytest.mark.asyncio
    async def test_list_all_pagination(self, store: ThesisStore) -> None:
        """Should support limit and offset."""
        await store.create(_card_data(ticker="QQQ"))
        await store.create(_card_data(ticker="SPY"))
        await store.create(_card_data(ticker="AAPL"))

        page1 = await store.list_all(limit=2, offset=0)
        assert len(page1) == 2

        page2 = await store.list_all(limit=2, offset=2)
        assert len(page2) == 1
