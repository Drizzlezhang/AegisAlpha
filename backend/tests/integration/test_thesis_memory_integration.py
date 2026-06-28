"""Integration tests — Thesis + Memory: episodic write + WeightAdapter trigger on close."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from aegis.services.thesis_service import ThesisService


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockThesisCard:
    """Minimal mock of ThesisCard ORM object."""

    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", 1)
        self.ticker = kwargs.get("ticker", "QQQ")
        self.direction = kwargs.get("direction", "long")
        self.entry_mode = kwargs.get("entry_mode", "active_right")
        self.entry_date = kwargs.get("entry_date", datetime(2026, 5, 1, tzinfo=timezone.utc))
        self.entry_price = kwargs.get("entry_price", 450.0)
        self.target_price = kwargs.get("target_price", 500.0)
        self.stop_price = kwargs.get("stop_price", 420.0)
        self.key_assumptions = kwargs.get("key_assumptions", ["QQQ above 200MA", "tech momentum"])
        self.thesis_valid_status = kwargs.get("thesis_valid_status", "valid")
        self.re_entry_flagged = kwargs.get("re_entry_flagged", False)
        self.factor_snapshot = kwargs.get("factor_snapshot", {"trend_phase": 75, "levels": 65})
        self.close_date = kwargs.get("close_date", None)
        self.close_price = kwargs.get("close_price", None)
        self.actual_pnl_pct = kwargs.get("actual_pnl_pct", None)
        self.judgment_score = kwargs.get("judgment_score", None)
        self.execution_score = kwargs.get("execution_score", None)
        self.close_reason = kwargs.get("close_reason", None)
        self.created_at = kwargs.get("created_at", datetime(2026, 5, 1, tzinfo=timezone.utc))


def _make_card(**kwargs: Any) -> MockThesisCard:
    return MockThesisCard(**kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_store() -> AsyncMock:
    store = AsyncMock()
    store.create = AsyncMock(return_value=1)
    store.get_by_id = AsyncMock(return_value=_make_card())
    store.get_active = AsyncMock(return_value=[])
    store.get_closed_with_scores = AsyncMock(return_value=[])
    store.get_recently_closed = AsyncMock(return_value=[])
    store.update = AsyncMock()
    store.close = AsyncMock()
    store.list_all = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_memory() -> AsyncMock:
    memory = AsyncMock()
    memory.read = AsyncMock(return_value=[])
    memory.write = AsyncMock()
    memory.search = AsyncMock(return_value=[])
    memory.summarize = AsyncMock(return_value={})
    memory.archive_scratchpad = AsyncMock()
    return memory


@pytest.fixture
def mock_weight_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.update_weights = MagicMock(return_value={"trend_phase": 80, "levels": 70})
    return adapter


@pytest.fixture
def mock_long_term_store() -> MagicMock:
    store = MagicMock()
    store.insert = MagicMock(return_value=100)
    return store


@pytest.fixture
def mock_session_factory() -> MagicMock:
    session = MagicMock()
    factory = MagicMock(return_value=session)
    return factory


@pytest.fixture
def thesis_service(
    mock_store: AsyncMock,
    mock_memory: AsyncMock,
    mock_weight_adapter: MagicMock,
    mock_long_term_store: MagicMock,
    mock_session_factory: MagicMock,
) -> ThesisService:
    return ThesisService(
        thesis_store=mock_store,
        memory=mock_memory,
        weight_adapter=mock_weight_adapter,
        long_term_store=mock_long_term_store,
        session_factory=mock_session_factory,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestThesisMemoryIntegration:
    """Verify episodic memory write and WeightAdapter trigger on thesis close."""

    @pytest.mark.asyncio
    async def test_close_writes_episodic_memory(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_long_term_store: MagicMock,
    ) -> None:
        """Should write episodic_thesis to LongTermStore on close."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(
                direction="long",
                entry_price=450.0,
                entry_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
                factor_snapshot={"trend_phase": 75, "levels": 65},
                key_assumptions=["QQQ above 200MA", "tech momentum strong"],
            )
        )

        await thesis_service.close_thesis(
            thesis_id=1,
            close_price=500.0,
            judgment_score=4,
            execution_score=3,
            close_reason="target_reached",
        )

        # Verify LongTermStore.insert was called
        mock_long_term_store.insert.assert_called_once()
        insert_args = mock_long_term_store.insert.call_args[0][0]

        # Check data_type
        assert insert_args["data_type"] == "episodic_thesis"
        assert insert_args["ticker"] == "QQQ"

        # Check content fields
        content = insert_args["content"]
        assert content["thesis_id"] == 1
        assert content["ticker"] == "QQQ"
        assert content["direction"] == "long"
        assert content["entry_price"] == 450.0
        assert content["close_price"] == 500.0
        assert pytest.approx(content["actual_pnl_pct"], rel=0.01) == 0.1111
        assert content["judgment_score"] == 4
        assert content["execution_score"] == 3
        assert content["close_reason"] == "target_reached"
        assert content["factor_snapshot"] == {"trend_phase": 75, "levels": 65}
        assert "QQQ above 200MA" in content["key_assumptions"]
        assert "tech momentum strong" in content["key_assumptions"]
        assert content["holding_days"] > 0

    @pytest.mark.asyncio
    async def test_close_triggers_weight_adapter(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_weight_adapter: MagicMock,
    ) -> None:
        """Should call WeightAdapter.update_weights on close."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="long", entry_price=450.0)
        )

        result = await thesis_service.close_thesis(
            thesis_id=1,
            close_price=500.0,
            judgment_score=4,
            execution_score=3,
            close_reason="target_reached",
        )

        mock_weight_adapter.update_weights.assert_called_once()
        assert result["new_weights"] == {"trend_phase": 80, "levels": 70}

    @pytest.mark.asyncio
    async def test_close_episodic_memory_contains_holding_days(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_long_term_store: MagicMock,
    ) -> None:
        """Should compute correct holding_days in episodic memory."""
        # Entry was 50 days ago
        entry = datetime.now(timezone.utc) - timedelta(days=50)
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(
                direction="long",
                entry_price=450.0,
                entry_date=entry,
            )
        )

        await thesis_service.close_thesis(
            thesis_id=1,
            close_price=500.0,
            judgment_score=4,
            execution_score=3,
            close_reason="target_reached",
        )

        content = mock_long_term_store.insert.call_args[0][0]["content"]
        assert content["holding_days"] == 50

    @pytest.mark.asyncio
    async def test_close_episodic_memory_short_put_pnl(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_long_term_store: MagicMock,
    ) -> None:
        """Should compute correct PnL for short_put in episodic memory."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="short_put", entry_price=10.0)
        )

        await thesis_service.close_thesis(
            thesis_id=1,
            close_price=8.0,
            judgment_score=4,
            execution_score=4,
            close_reason="target_reached",
        )

        content = mock_long_term_store.insert.call_args[0][0]["content"]
        # short_put PnL: (10 - 8) / 10 = 0.2
        assert pytest.approx(content["actual_pnl_pct"], rel=0.01) == 0.2

    @pytest.mark.asyncio
    async def test_close_episodic_memory_cc_pnl(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_long_term_store: MagicMock,
    ) -> None:
        """Should compute correct PnL for cc in episodic memory."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="cc", entry_price=5.0)
        )

        await thesis_service.close_thesis(
            thesis_id=1,
            close_price=3.0,
            judgment_score=4,
            execution_score=4,
            close_reason="target_reached",
        )

        content = mock_long_term_store.insert.call_args[0][0]["content"]
        # cc PnL: (5 - 3) / 5 = 0.4
        assert pytest.approx(content["actual_pnl_pct"], rel=0.01) == 0.4

    @pytest.mark.asyncio
    async def test_close_episodic_memory_negative_pnl(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_long_term_store: MagicMock,
    ) -> None:
        """Should record negative PnL correctly in episodic memory."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="long", entry_price=450.0)
        )

        await thesis_service.close_thesis(
            thesis_id=1,
            close_price=400.0,
            judgment_score=2,
            execution_score=2,
            close_reason="stop_hit",
        )

        content = mock_long_term_store.insert.call_args[0][0]["content"]
        # PnL: (400 - 450) / 450 = -0.1111
        assert pytest.approx(content["actual_pnl_pct"], rel=0.01) == -0.1111
        assert content["judgment_score"] == 2
        assert content["execution_score"] == 2
        assert content["close_reason"] == "stop_hit"

    @pytest.mark.asyncio
    async def test_close_episodic_memory_original_date_is_utc(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_long_term_store: MagicMock,
    ) -> None:
        """Should set original_date to UTC datetime in episodic memory."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="long", entry_price=450.0)
        )

        await thesis_service.close_thesis(
            thesis_id=1,
            close_price=500.0,
            judgment_score=4,
            execution_score=3,
            close_reason="target_reached",
        )

        insert_args = mock_long_term_store.insert.call_args[0][0]
        original_date = insert_args["original_date"]
        assert original_date.tzinfo is not None
        assert original_date.tzinfo == UTC

    @pytest.mark.asyncio
    async def test_close_episodic_memory_entry_date_isoformat(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_long_term_store: MagicMock,
    ) -> None:
        """Should store entry_date as ISO format string in episodic memory."""
        entry = datetime(2026, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="long", entry_price=450.0, entry_date=entry)
        )

        await thesis_service.close_thesis(
            thesis_id=1,
            close_price=500.0,
            judgment_score=4,
            execution_score=3,
            close_reason="target_reached",
        )

        content = mock_long_term_store.insert.call_args[0][0]["content"]
        assert content["entry_date"] == "2026-03-15T10:30:00+00:00"

    @pytest.mark.asyncio
    async def test_weight_adapter_receives_session(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_weight_adapter: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """Should pass a Session to WeightAdapter.update_weights."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="long", entry_price=450.0)
        )

        await thesis_service.close_thesis(
            thesis_id=1,
            close_price=500.0,
            judgment_score=4,
            execution_score=3,
            close_reason="target_reached",
        )

        mock_weight_adapter.update_weights.assert_called_once()
        # The session passed should be from our factory
        call_session = mock_weight_adapter.update_weights.call_args[0][0]
        assert call_session is mock_session_factory.return_value

    @pytest.mark.asyncio
    async def test_weight_adapter_session_closed_after_use(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """Should close the session after WeightAdapter.update_weights."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="long", entry_price=450.0)
        )

        await thesis_service.close_thesis(
            thesis_id=1,
            close_price=500.0,
            judgment_score=4,
            execution_score=3,
            close_reason="target_reached",
        )

        mock_session_factory.return_value.close.assert_called_once()
