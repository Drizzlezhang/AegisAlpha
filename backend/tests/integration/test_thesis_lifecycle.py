"""Integration tests — Thesis complete lifecycle: create → validate → close → Memory → WeightAdapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
        self.factor_snapshot = kwargs.get("factor_snapshot", {"trend_phase": 75})
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
    store.insert = MagicMock()
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


class TestThesisLifecycle:
    """End-to-end thesis lifecycle: create → validate → close → memory → weight."""

    @pytest.mark.asyncio
    async def test_create_from_recommendation(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should create a ThesisCard from a recommendation dict."""
        rec = {
            "ticker": "QQQ",
            "direction": "long",
            "entry_mode": "active_right",
            "entry_price": 450.0,
            "target_price": 500.0,
            "stop_price": 420.0,
            "key_assumptions": ["QQQ above 200MA", "tech momentum strong"],
        }
        weight_snapshot = {"trend_phase": 75, "levels": 65}

        thesis_id = await thesis_service.create_from_recommendation(rec, weight_snapshot)

        assert thesis_id == 1
        mock_store.create.assert_called_once()
        call_args = mock_store.create.call_args[0][0]
        assert call_args["ticker"] == "QQQ"
        assert call_args["direction"] == "long"
        assert call_args["entry_mode"] == "active_right"
        assert call_args["entry_price"] == 450.0
        assert call_args["thesis_valid_status"] == "valid"
        assert call_args["re_entry_flagged"] is False
        assert call_args["factor_snapshot"] == weight_snapshot

    @pytest.mark.asyncio
    async def test_create_rejects_duplicate_active(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should reject creation when active thesis exists for ticker."""
        mock_store.get_active = AsyncMock(return_value=[_make_card()])

        rec = {
            "ticker": "QQQ",
            "direction": "long",
            "entry_price": 450.0,
            "key_assumptions": ["test"],
        }

        with pytest.raises(ValueError, match="Active thesis already exists"):
            await thesis_service.create_from_recommendation(rec, {})

    @pytest.mark.asyncio
    async def test_create_requires_user_confirmation(
        self, thesis_service: ThesisService
    ) -> None:
        """Should reject creation without user confirmation."""
        rec = {"ticker": "QQQ", "direction": "long", "entry_price": 450.0, "key_assumptions": []}

        with pytest.raises(ValueError, match="User must confirm"):
            await thesis_service.create_from_recommendation(rec, {}, user_confirmed=False)

    @pytest.mark.asyncio
    async def test_close_thesis_computes_pnl_long(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_weight_adapter: MagicMock,
        mock_long_term_store: MagicMock,
    ) -> None:
        """Should compute correct PnL for long direction and trigger weight update."""
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

        # PnL: (500 - 450) / 450 = 0.1111...
        assert result["thesis_id"] == 1
        assert pytest.approx(result["pnl_pct"], rel=0.01) == 0.1111
        assert "new_weights" in result

        # Verify close was called
        mock_store.close.assert_called_once()
        close_args = mock_store.close.call_args[0][1]
        assert close_args["close_price"] == 500.0
        assert close_args["judgment_score"] == 4
        assert close_args["execution_score"] == 3
        assert close_args["close_reason"] == "target_reached"

        # Verify WeightAdapter was triggered
        mock_weight_adapter.update_weights.assert_called_once()

        # Verify episodic memory was written
        mock_long_term_store.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_thesis_computes_pnl_cc(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
    ) -> None:
        """Should compute correct PnL for covered_call direction."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="cc", entry_price=5.0)
        )

        result = await thesis_service.close_thesis(
            thesis_id=1,
            close_price=3.0,
            judgment_score=4,
            execution_score=4,
            close_reason="target_reached",
        )

        # PnL for cc: (5 - 3) / 5 = 0.4
        assert pytest.approx(result["pnl_pct"], rel=0.01) == 0.4

    @pytest.mark.asyncio
    async def test_close_rejects_invalid_scores(
        self, thesis_service: ThesisService
    ) -> None:
        """Should reject scores outside 1-5 range."""
        with pytest.raises(ValueError, match="judgment_score must be 1-5"):
            await thesis_service.close_thesis(1, 500.0, 0, 3, "manual")

        with pytest.raises(ValueError, match="execution_score must be 1-5"):
            await thesis_service.close_thesis(1, 500.0, 3, 6, "manual")

    @pytest.mark.asyncio
    async def test_close_rejects_already_closed(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should reject closing an already-closed thesis."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(close_date=datetime(2026, 5, 15, tzinfo=timezone.utc))
        )

        with pytest.raises(ValueError, match="already closed"):
            await thesis_service.close_thesis(1, 500.0, 3, 3, "manual")

    @pytest.mark.asyncio
    async def test_close_thesis_not_found(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should reject closing a non-existent thesis."""
        mock_store.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await thesis_service.close_thesis(999, 500.0, 3, 3, "manual")

    @pytest.mark.asyncio
    async def test_update_valid_status_one_way(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should enforce one-way status transitions (no rollback)."""
        # Start at valid
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(thesis_valid_status="valid")
        )

        await thesis_service.update_valid_status(1, "partial_broken")
        mock_store.update.assert_called_with(1, {"thesis_valid_status": "partial_broken"})

        # Now try to roll back
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(thesis_valid_status="partial_broken")
        )
        mock_store.update.reset_mock()

        await thesis_service.update_valid_status(1, "valid")
        mock_store.update.assert_not_called()  # Rollback blocked

    @pytest.mark.asyncio
    async def test_update_valid_status_marks_broken_assumptions(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should mark broken assumptions with [BROKEN] prefix."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(
                thesis_valid_status="valid",
                key_assumptions=["QQQ above 200MA", "tech momentum", "low VIX"],
            )
        )

        await thesis_service.update_valid_status(
            1, "fully_broken", broken_assumptions=["QQQ above 200MA", "low VIX"]
        )

        call_args = mock_store.update.call_args[0][1]
        assert "[BROKEN] QQQ above 200MA" in call_args["key_assumptions"]
        assert "[BROKEN] low VIX" in call_args["key_assumptions"]
        assert "tech momentum" in call_args["key_assumptions"]
        assert "[BROKEN] tech momentum" not in call_args["key_assumptions"]

    @pytest.mark.asyncio
    async def test_update_valid_status_skips_closed(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should skip status update for already-closed thesis."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(close_date=datetime(2026, 5, 15, tzinfo=timezone.utc))
        )

        await thesis_service.update_valid_status(1, "fully_broken")
        mock_store.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_has_active_thesis(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should correctly report active thesis existence."""
        mock_store.get_active = AsyncMock(return_value=[])
        assert await thesis_service.has_active_thesis("QQQ") is False

        mock_store.get_active = AsyncMock(return_value=[_make_card()])
        assert await thesis_service.has_active_thesis("QQQ") is True

    @pytest.mark.asyncio
    async def test_check_re_entry_conditions(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should flag re-entry when conditions are met."""
        # No active thesis
        mock_store.get_active = AsyncMock(return_value=[])

        # Recently closed with good score, >30 days ago
        closed_card = _make_card(
            id=5,
            close_date=datetime.now(timezone.utc) - timedelta(days=45),
            judgment_score=4,
        )
        mock_store.get_recently_closed = AsyncMock(return_value=[closed_card])

        result = await thesis_service.check_re_entry("QQQ")
        assert result is True
        mock_store.update.assert_called_with(5, {"re_entry_flagged": True})

    @pytest.mark.asyncio
    async def test_check_re_entry_blocked_by_active(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should not flag re-entry when active thesis exists."""
        mock_store.get_active = AsyncMock(return_value=[_make_card()])

        result = await thesis_service.check_re_entry("QQQ")
        assert result is False
        mock_store.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_re_entry_low_score(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should not flag re-entry when judgment_score < 3."""
        mock_store.get_active = AsyncMock(return_value=[])

        closed_card = _make_card(
            id=5,
            close_date=datetime.now(timezone.utc) - timedelta(days=45),
            judgment_score=2,
        )
        mock_store.get_recently_closed = AsyncMock(return_value=[closed_card])

        result = await thesis_service.check_re_entry("QQQ")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_re_entry_too_recent(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should not flag re-entry when closed < 30 days ago."""
        mock_store.get_active = AsyncMock(return_value=[])

        closed_card = _make_card(
            id=5,
            close_date=datetime.now(timezone.utc) - timedelta(days=10),
            judgment_score=4,
        )
        mock_store.get_recently_closed = AsyncMock(return_value=[closed_card])

        result = await thesis_service.check_re_entry("QQQ")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_active_theses(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should return active theses as dicts."""
        mock_store.get_active = AsyncMock(return_value=[_make_card(id=1), _make_card(id=2)])

        result = await thesis_service.get_active_theses()
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_get_closed_with_scores(
        self, thesis_service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should delegate to store.get_closed_with_scores."""
        mock_store.get_closed_with_scores = AsyncMock(
            return_value=[{"id": 1, "judgment_score": 4, "execution_score": 3}]
        )

        result = await thesis_service.get_closed_with_scores()
        assert len(result) == 1
        assert result[0]["judgment_score"] == 4

    @pytest.mark.asyncio
    async def test_close_thesis_weight_adapter_failure_non_blocking(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_weight_adapter: MagicMock,
    ) -> None:
        """Should not block close_thesis when WeightAdapter fails."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="long", entry_price=450.0)
        )
        mock_weight_adapter.update_weights = MagicMock(
            side_effect=RuntimeError("DB connection lost")
        )

        result = await thesis_service.close_thesis(
            thesis_id=1,
            close_price=500.0,
            judgment_score=4,
            execution_score=3,
            close_reason="target_reached",
        )

        # Should still succeed with empty weights
        assert result["thesis_id"] == 1
        assert result["new_weights"] == {}
        mock_store.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_thesis_episodic_memory_failure_non_blocking(
        self,
        thesis_service: ThesisService,
        mock_store: AsyncMock,
        mock_long_term_store: MagicMock,
    ) -> None:
        """Should not block close_thesis when episodic memory write fails."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="long", entry_price=450.0)
        )
        mock_long_term_store.insert = MagicMock(side_effect=RuntimeError("DB error"))

        result = await thesis_service.close_thesis(
            thesis_id=1,
            close_price=500.0,
            judgment_score=4,
            execution_score=3,
            close_reason="target_reached",
        )

        assert result["thesis_id"] == 1
        mock_store.close.assert_called_once()
