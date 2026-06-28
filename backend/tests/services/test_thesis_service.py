"""Tests for ThesisService — lifecycle management: create, close, validate, re-entry."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
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
    store.get_earliest_card = AsyncMock(return_value=None)
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
    adapter.update_weights = MagicMock(return_value={"trend_phase": 1.2})
    return adapter


@pytest.fixture
def mock_long_term() -> MagicMock:
    store = MagicMock()
    store.insert = MagicMock(return_value=1)
    return store


@pytest.fixture
def mock_session_factory() -> MagicMock:
    session = MagicMock()
    factory = MagicMock(return_value=session)
    return factory


@pytest.fixture
def service(
    mock_store: AsyncMock,
    mock_memory: AsyncMock,
    mock_weight_adapter: MagicMock,
    mock_long_term: MagicMock,
    mock_session_factory: MagicMock,
) -> ThesisService:
    return ThesisService(
        thesis_store=mock_store,
        memory=mock_memory,
        weight_adapter=mock_weight_adapter,
        long_term_store=mock_long_term,
        session_factory=mock_session_factory,
    )


def _recommendation(**overrides: Any) -> dict[str, Any]:
    base = {
        "ticker": "QQQ",
        "direction": "long",
        "entry_mode": "active_right",
        "entry_price": 450.0,
        "target_price": 500.0,
        "stop_price": 420.0,
        "key_assumptions": ["QQQ above 200MA", "tech momentum"],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateFromRecommendation:
    @pytest.mark.asyncio
    async def test_create_success(self, service: ThesisService, mock_store: AsyncMock) -> None:
        """Should create a ThesisCard from a recommendation."""
        rec = _recommendation()
        thesis_id = await service.create_from_recommendation(rec, {"trend_phase": 75})

        assert thesis_id == 1
        mock_store.create.assert_called_once()
        call_args = mock_store.create.call_args[0][0]
        assert call_args["ticker"] == "QQQ"
        assert call_args["direction"] == "long"
        assert call_args["entry_price"] == 450.0
        assert call_args["thesis_valid_status"] == "valid"
        assert call_args["re_entry_flagged"] is False
        assert call_args["factor_snapshot"] == {"trend_phase": 75}

    @pytest.mark.asyncio
    async def test_create_duplicate_active(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should raise ValueError when active thesis exists for same ticker."""
        mock_store.get_active = AsyncMock(return_value=[_make_card()])
        rec = _recommendation()

        with pytest.raises(ValueError, match="Active thesis already exists"):
            await service.create_from_recommendation(rec, {})

    @pytest.mark.asyncio
    async def test_create_not_confirmed(self, service: ThesisService) -> None:
        """Should raise ValueError when user has not confirmed."""
        rec = _recommendation()

        with pytest.raises(ValueError, match="User must confirm"):
            await service.create_from_recommendation(rec, {}, user_confirmed=False)


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------


class TestCloseThesis:
    @pytest.mark.asyncio
    async def test_close_long_profit(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """PnL for long: (close - entry) / entry."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="long", entry_price=450.0)
        )

        result = await service.close_thesis(1, 480.0, 4, 3, "target_reached")

        expected_pnl = (480.0 - 450.0) / 450.0
        assert result["pnl_pct"] == pytest.approx(expected_pnl)
        assert result["thesis_id"] == 1
        mock_store.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_short_put_pnl(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """PnL for short_put: (entry - close) / entry."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="short_put", entry_price=450.0)
        )

        result = await service.close_thesis(1, 430.0, 3, 4, "manual")

        expected_pnl = (450.0 - 430.0) / 450.0
        assert result["pnl_pct"] == pytest.approx(expected_pnl)

    @pytest.mark.asyncio
    async def test_close_cc_pnl(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """PnL for cc: (entry - close) / entry."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="cc", entry_price=450.0)
        )

        result = await service.close_thesis(1, 460.0, 4, 4, "target_reached")

        expected_pnl = (450.0 - 460.0) / 450.0
        assert result["pnl_pct"] == pytest.approx(expected_pnl)

    @pytest.mark.asyncio
    async def test_close_invalid_judgment_score(self, service: ThesisService) -> None:
        """Should raise ValueError for judgment_score outside 1-5."""
        with pytest.raises(ValueError, match="judgment_score must be 1-5"):
            await service.close_thesis(1, 480.0, 0, 3)

        with pytest.raises(ValueError, match="judgment_score must be 1-5"):
            await service.close_thesis(1, 480.0, 6, 3)

    @pytest.mark.asyncio
    async def test_close_invalid_execution_score(self, service: ThesisService) -> None:
        """Should raise ValueError for execution_score outside 1-5."""
        with pytest.raises(ValueError, match="execution_score must be 1-5"):
            await service.close_thesis(1, 480.0, 3, 0)

    @pytest.mark.asyncio
    async def test_close_not_found(self, service: ThesisService, mock_store: AsyncMock) -> None:
        """Should raise ValueError when thesis not found."""
        mock_store.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await service.close_thesis(999, 480.0, 3, 3)

    @pytest.mark.asyncio
    async def test_close_already_closed(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should raise ValueError when thesis is already closed."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(close_date=datetime(2026, 6, 1, tzinfo=timezone.utc))
        )

        with pytest.raises(ValueError, match="already closed"):
            await service.close_thesis(1, 480.0, 3, 3)

    @pytest.mark.asyncio
    async def test_close_writes_episodic_memory(
        self,
        service: ThesisService,
        mock_store: AsyncMock,
        mock_long_term: MagicMock,
    ) -> None:
        """Should write episodic memory on close."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="long", entry_price=450.0)
        )

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs) if callable(fn) else None
            await service.close_thesis(1, 480.0, 4, 3, "target_reached")

        # LongTermStore.insert should have been called via asyncio.to_thread
        assert mock_long_term.insert.called

    @pytest.mark.asyncio
    async def test_close_triggers_weight_adapter(
        self,
        service: ThesisService,
        mock_store: AsyncMock,
        mock_weight_adapter: MagicMock,
    ) -> None:
        """Should trigger WeightAdapter on close."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(direction="long", entry_price=450.0)
        )

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs) if callable(fn) else None
            result = await service.close_thesis(1, 480.0, 4, 3, "target_reached")

        assert "new_weights" in result


# ---------------------------------------------------------------------------
# Validation status
# ---------------------------------------------------------------------------


class TestUpdateValidStatus:
    @pytest.mark.asyncio
    async def test_valid_to_partial_broken(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should transition valid → partial_broken."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(thesis_valid_status="valid")
        )

        await service.update_valid_status(1, "partial_broken", ["QQQ above 200MA"])

        mock_store.update.assert_called_once()
        update_data = mock_store.update.call_args[0][1]
        assert update_data["thesis_valid_status"] == "partial_broken"
        assert "[BROKEN] QQQ above 200MA" in update_data["key_assumptions"]

    @pytest.mark.asyncio
    async def test_no_rollback(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should ignore rollback from fully_broken → valid."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(thesis_valid_status="fully_broken")
        )

        await service.update_valid_status(1, "valid")

        # update should NOT be called (rollback ignored)
        mock_store.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_closed_skips(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should skip validation for already closed thesis."""
        mock_store.get_by_id = AsyncMock(
            return_value=_make_card(
                thesis_valid_status="valid",
                close_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
            )
        )

        await service.update_valid_status(1, "fully_broken")

        mock_store.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_status_raises(self, service: ThesisService) -> None:
        """Should raise ValueError for invalid status string."""
        with pytest.raises(ValueError, match="Invalid status"):
            await service.update_valid_status(1, "unknown_status")

    @pytest.mark.asyncio
    async def test_not_found_raises(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should raise ValueError when thesis not found."""
        mock_store.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await service.update_valid_status(999, "partial_broken")


# ---------------------------------------------------------------------------
# Re-entry check
# ---------------------------------------------------------------------------


class TestCheckReEntry:
    @pytest.mark.asyncio
    async def test_conditions_met(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should flag re-entry when: ≥30 days, judgment≥3, no active thesis."""
        mock_store.get_active = AsyncMock(return_value=[])
        closed_card = _make_card(
            id=5,
            close_date=datetime.now(timezone.utc) - timedelta(days=45),
            judgment_score=4,
        )
        mock_store.get_recently_closed = AsyncMock(return_value=[closed_card])

        result = await service.check_re_entry("QQQ")

        assert result is True
        mock_store.update.assert_called_once_with(5, {"re_entry_flagged": True})

    @pytest.mark.asyncio
    async def test_active_thesis_blocks(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should return False when active thesis exists."""
        mock_store.get_active = AsyncMock(return_value=[_make_card()])

        result = await service.check_re_entry("QQQ")

        assert result is False
        mock_store.get_recently_closed.assert_not_called()

    @pytest.mark.asyncio
    async def test_less_than_30_days(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should return False when closed < 30 days ago."""
        mock_store.get_active = AsyncMock(return_value=[])
        closed_card = _make_card(
            close_date=datetime.now(timezone.utc) - timedelta(days=10),
            judgment_score=4,
        )
        mock_store.get_recently_closed = AsyncMock(return_value=[closed_card])

        result = await service.check_re_entry("QQQ")

        assert result is False

    @pytest.mark.asyncio
    async def test_low_judgment_score(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should return False when judgment_score < 3."""
        mock_store.get_active = AsyncMock(return_value=[])
        closed_card = _make_card(
            close_date=datetime.now(timezone.utc) - timedelta(days=45),
            judgment_score=2,
        )
        mock_store.get_recently_closed = AsyncMock(return_value=[closed_card])

        result = await service.check_re_entry("QQQ")

        assert result is False


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


class TestQueries:
    @pytest.mark.asyncio
    async def test_has_active_thesis_true(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should return True when active thesis exists."""
        mock_store.get_active = AsyncMock(return_value=[_make_card()])

        result = await service.has_active_thesis("QQQ")

        assert result is True

    @pytest.mark.asyncio
    async def test_has_active_thesis_false(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should return False when no active thesis."""
        mock_store.get_active = AsyncMock(return_value=[])

        result = await service.has_active_thesis("QQQ")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_active_theses(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should return list of active thesis dicts."""
        mock_store.get_active = AsyncMock(return_value=[_make_card()])

        result = await service.get_active_theses()

        assert len(result) == 1
        assert result[0]["ticker"] == "QQQ"
        assert result[0]["thesis_valid_status"] == "valid"

    @pytest.mark.asyncio
    async def test_get_closed_with_scores(
        self, service: ThesisService, mock_store: AsyncMock
    ) -> None:
        """Should delegate to store.get_closed_with_scores."""
        mock_store.get_closed_with_scores = AsyncMock(
            return_value=[{"id": 1, "ticker": "QQQ", "judgment_score": 4}]
        )

        result = await service.get_closed_with_scores()

        assert len(result) == 1
        assert result[0]["judgment_score"] == 4
