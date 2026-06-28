"""Tests for KOLAttributionService — 30d/60d attribution and reliability updates."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis.services.kol_attribution import KOLAttributionService
from aegis.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockKOLCall:
    """Minimal mock of KOLCall ORM object."""

    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", 1)
        self.kol_source_id = kwargs.get("kol_source_id", 1)
        self.ticker = kwargs.get("ticker", "QQQ")
        self.direction = kwargs.get("direction", "bullish")
        self.call_date = kwargs.get("call_date", None)
        self.call_price = kwargs.get("call_price", 450.0)
        self.attribution_status = kwargs.get("attribution_status", "pending")
        self.pnl_30d = kwargs.get("pnl_30d", None)
        self.pnl_60d = kwargs.get("pnl_60d", None)
        self.source_url = kwargs.get("source_url", "")
        self.content_snippet = kwargs.get("content_snippet", "")


class MockKOLSource:
    """Minimal mock of KOLSource ORM object."""

    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", 1)
        self.name = kwargs.get("name", "test_kol")
        self.platform = kwargs.get("platform", "x")
        self.handle = kwargs.get("handle", "testuser")
        self.reliability_score = kwargs.get("reliability_score", 0.5)
        self.total_calls = kwargs.get("total_calls", 10)
        self.successful_calls = kwargs.get("successful_calls", 5)
        self.enabled = kwargs.get("enabled", True)


def _mock_price_fetcher(price: float | None = 500.0) -> MagicMock:
    """Create a mock price fetcher that returns the given price."""
    mock = MagicMock()
    mock.fetch = AsyncMock(
        return_value=ToolResult(
            success=True,
            data={"ticker": "QQQ", "price": price},
            source="yfinance",
        )
    )
    return mock


def _mock_price_fetcher_failing() -> MagicMock:
    """Create a mock price fetcher that always fails."""
    mock = MagicMock()
    mock.fetch = AsyncMock(
        return_value=ToolResult(success=False, error="API error", source="yfinance")
    )
    return mock


# ---------------------------------------------------------------------------
# 30-day attribution tests
# ---------------------------------------------------------------------------


class Test30DayAttribution:
    @pytest.mark.asyncio
    async def test_bullish_validated(self) -> None:
        """Bullish call with +10% P&L should be validated."""
        store = MagicMock()
        store.get_pending_attribution = AsyncMock(
            return_value=[MockKOLCall(direction="bullish", call_price=450.0)]
        )
        store.update_attribution = AsyncMock()
        store.get_source = AsyncMock(
            return_value=MockKOLSource(reliability_score=0.5)
        )
        store.update_source = AsyncMock()

        price_fetcher = _mock_price_fetcher(price=500.0)  # +11.1%
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        stats = await service.run_30d_attribution()

        assert stats["validated"] == 1
        assert stats["invalidated"] == 0
        store.update_attribution.assert_called_once()
        # Verify status is "validated"
        call_args = store.update_attribution.call_args
        assert call_args[0][1] == "validated"

    @pytest.mark.asyncio
    async def test_bullish_invalidated(self) -> None:
        """Bullish call with +2% P&L (below threshold) should be invalidated."""
        store = MagicMock()
        store.get_pending_attribution = AsyncMock(
            return_value=[MockKOLCall(direction="bullish", call_price=450.0)]
        )
        store.update_attribution = AsyncMock()
        store.get_source = AsyncMock(
            return_value=MockKOLSource(reliability_score=0.5)
        )
        store.update_source = AsyncMock()

        price_fetcher = _mock_price_fetcher(price=460.0)  # +2.2%
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        stats = await service.run_30d_attribution()

        assert stats["invalidated"] == 1
        call_args = store.update_attribution.call_args
        assert call_args[0][1] == "invalidated"

    @pytest.mark.asyncio
    async def test_bearish_validated(self) -> None:
        """Bearish call with -10% P&L should be validated."""
        store = MagicMock()
        store.get_pending_attribution = AsyncMock(
            return_value=[MockKOLCall(direction="bearish", call_price=500.0)]
        )
        store.update_attribution = AsyncMock()
        store.get_source = AsyncMock(
            return_value=MockKOLSource(reliability_score=0.5)
        )
        store.update_source = AsyncMock()

        price_fetcher = _mock_price_fetcher(price=440.0)  # -12%
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        stats = await service.run_30d_attribution()

        assert stats["validated"] == 1
        call_args = store.update_attribution.call_args
        assert call_args[0][1] == "validated"

    @pytest.mark.asyncio
    async def test_bearish_invalidated(self) -> None:
        """Bearish call with +3% P&L (price went up) should be invalidated."""
        store = MagicMock()
        store.get_pending_attribution = AsyncMock(
            return_value=[MockKOLCall(direction="bearish", call_price=500.0)]
        )
        store.update_attribution = AsyncMock()
        store.get_source = AsyncMock(
            return_value=MockKOLSource(reliability_score=0.5)
        )
        store.update_source = AsyncMock()

        price_fetcher = _mock_price_fetcher(price=515.0)  # +3%
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        stats = await service.run_30d_attribution()

        assert stats["invalidated"] == 1

    @pytest.mark.asyncio
    async def test_no_pending_calls(self) -> None:
        """Should return empty stats when no pending calls."""
        store = MagicMock()
        store.get_pending_attribution = AsyncMock(return_value=[])

        service = KOLAttributionService(kol_store=store)
        stats = await service.run_30d_attribution()

        assert stats["total"] == 0
        assert stats["validated"] == 0

    @pytest.mark.asyncio
    async def test_price_unavailable_skipped(self) -> None:
        """Calls with unavailable price should be skipped."""
        store = MagicMock()
        store.get_pending_attribution = AsyncMock(
            return_value=[MockKOLCall(direction="bullish", call_price=450.0)]
        )
        store.update_attribution = AsyncMock()

        price_fetcher = _mock_price_fetcher_failing()
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        stats = await service.run_30d_attribution()

        assert stats["skipped"] == 1
        store.update_attribution.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_pending_attribution_failure(self) -> None:
        """Should handle store failure gracefully."""
        store = MagicMock()
        store.get_pending_attribution = AsyncMock(side_effect=RuntimeError("DB down"))

        service = KOLAttributionService(kol_store=store)
        stats = await service.run_30d_attribution()

        assert stats["total"] == 0

    @pytest.mark.asyncio
    async def test_ema_reliability_update(self) -> None:
        """Reliability should be updated via EMA: new = 0.9*old + 0.1*validated."""
        store = MagicMock()
        store.get_pending_attribution = AsyncMock(
            return_value=[MockKOLCall(direction="bullish", call_price=450.0)]
        )
        store.update_attribution = AsyncMock()
        store.get_source = AsyncMock(
            return_value=MockKOLSource(reliability_score=0.5, total_calls=10, successful_calls=5)
        )
        store.update_source = AsyncMock()

        price_fetcher = _mock_price_fetcher(price=500.0)  # validated
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        await service.run_30d_attribution()

        # Verify reliability update: 0.9*0.5 + 0.1*1.0 = 0.55
        store.update_source.assert_called_once()
        call_args = store.update_source.call_args
        assert call_args[0][0] == 1  # source_id
        assert call_args[0][1]["reliability_score"] == pytest.approx(0.55, rel=1e-4)
        assert call_args[0][1]["total_calls"] == 11
        assert call_args[0][1]["successful_calls"] == 6

    @pytest.mark.asyncio
    async def test_ema_reliability_invalidated(self) -> None:
        """Invalidated call: new = 0.9*old + 0.1*0 = 0.9*old."""
        store = MagicMock()
        store.get_pending_attribution = AsyncMock(
            return_value=[MockKOLCall(direction="bullish", call_price=450.0)]
        )
        store.update_attribution = AsyncMock()
        store.get_source = AsyncMock(
            return_value=MockKOLSource(reliability_score=0.8, total_calls=20, successful_calls=15)
        )
        store.update_source = AsyncMock()

        price_fetcher = _mock_price_fetcher(price=460.0)  # +2.2%, invalidated
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        await service.run_30d_attribution()

        # new = 0.9*0.8 + 0.1*0 = 0.72
        call_args = store.update_source.call_args
        assert call_args[0][1]["reliability_score"] == pytest.approx(0.72, rel=1e-4)
        assert call_args[0][1]["successful_calls"] == 15  # unchanged

    @pytest.mark.asyncio
    async def test_reliability_clamped_to_0_1(self) -> None:
        """Reliability score should be clamped to [0, 1]."""
        store = MagicMock()
        store.get_pending_attribution = AsyncMock(
            return_value=[MockKOLCall(direction="bullish", call_price=450.0)]
        )
        store.update_attribution = AsyncMock()
        store.get_source = AsyncMock(
            return_value=MockKOLSource(reliability_score=0.99)
        )
        store.update_source = AsyncMock()

        price_fetcher = _mock_price_fetcher(price=500.0)  # validated
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        await service.run_30d_attribution()

        # new = 0.9*0.99 + 0.1*1.0 = 0.991, clamped to 1.0
        call_args = store.update_source.call_args
        assert call_args[0][1]["reliability_score"] <= 1.0
        assert call_args[0][1]["reliability_score"] >= 0.0

    @pytest.mark.asyncio
    async def test_source_not_found_graceful(self) -> None:
        """Should handle missing source gracefully."""
        store = MagicMock()
        store.get_pending_attribution = AsyncMock(
            return_value=[MockKOLCall(direction="bullish", call_price=450.0)]
        )
        store.update_attribution = AsyncMock()
        store.get_source = AsyncMock(return_value=None)
        store.update_source = AsyncMock()

        price_fetcher = _mock_price_fetcher(price=500.0)
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        stats = await service.run_30d_attribution()

        # Should still complete — attribution updated, reliability skipped
        assert stats["validated"] == 1
        store.update_source.assert_not_called()

    @pytest.mark.asyncio
    async def test_zero_call_price(self) -> None:
        """Call with zero call_price should not crash."""
        store = MagicMock()
        store.get_pending_attribution = AsyncMock(
            return_value=[MockKOLCall(direction="bullish", call_price=0.0)]
        )
        store.update_attribution = AsyncMock()
        store.get_source = AsyncMock(
            return_value=MockKOLSource(reliability_score=0.5)
        )
        store.update_source = AsyncMock()

        price_fetcher = _mock_price_fetcher(price=500.0)
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        stats = await service.run_30d_attribution()

        # P&L = 0%, below threshold → invalidated
        assert stats["invalidated"] == 1

    @pytest.mark.asyncio
    async def test_max_calls_cap(self) -> None:
        """Should cap processing at MAX_CALLS_PER_RUN."""
        store = MagicMock()
        # Create 250 pending calls
        calls = [MockKOLCall(id=i, direction="bullish", call_price=450.0) for i in range(250)]
        store.get_pending_attribution = AsyncMock(return_value=calls)
        store.update_attribution = AsyncMock()
        store.get_source = AsyncMock(
            return_value=MockKOLSource(reliability_score=0.5)
        )
        store.update_source = AsyncMock()

        price_fetcher = _mock_price_fetcher(price=500.0)
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        stats = await service.run_30d_attribution()

        # Should only process MAX_CALLS_PER_RUN (200)
        assert stats["total"] == 200
        assert store.update_attribution.call_count == 200


# ---------------------------------------------------------------------------
# 60-day supplementary tests
# ---------------------------------------------------------------------------


class Test60DaySupplementary:
    @pytest.mark.asyncio
    async def test_update_60d_pnl(self) -> None:
        """Should update 60d P&L for calls needing it."""
        store = MagicMock()
        store.get_calls_needing_60d_update = AsyncMock(
            return_value=[MockKOLCall(call_price=450.0)]
        )
        store.update_pnl_60d = AsyncMock()

        price_fetcher = _mock_price_fetcher(price=480.0)  # +6.67%
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        stats = await service.run_60d_supplementary()

        assert stats["updated"] == 1
        store.update_pnl_60d.assert_called_once()
        call_args = store.update_pnl_60d.call_args
        assert call_args[0][0] == 1  # call_id
        assert call_args[0][1] == pytest.approx(6.67, rel=1e-2)

    @pytest.mark.asyncio
    async def test_no_calls_needing_update(self) -> None:
        """Should return empty stats when no calls need 60d update."""
        store = MagicMock()
        store.get_calls_needing_60d_update = AsyncMock(return_value=[])

        service = KOLAttributionService(kol_store=store)
        stats = await service.run_60d_supplementary()

        assert stats["total"] == 0
        assert stats["updated"] == 0

    @pytest.mark.asyncio
    async def test_price_unavailable_skipped(self) -> None:
        """Calls with unavailable price should be skipped."""
        store = MagicMock()
        store.get_calls_needing_60d_update = AsyncMock(
            return_value=[MockKOLCall(call_price=450.0)]
        )
        store.update_pnl_60d = AsyncMock()

        price_fetcher = _mock_price_fetcher_failing()
        service = KOLAttributionService(kol_store=store, price_fetcher=price_fetcher)

        stats = await service.run_60d_supplementary()

        assert stats["skipped"] == 1
        store.update_pnl_60d.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_calls_failure(self) -> None:
        """Should handle store failure gracefully."""
        store = MagicMock()
        store.get_calls_needing_60d_update = AsyncMock(side_effect=RuntimeError("DB down"))

        service = KOLAttributionService(kol_store=store)
        stats = await service.run_60d_supplementary()

        assert stats["total"] == 0


# ---------------------------------------------------------------------------
# Attribution report tests
# ---------------------------------------------------------------------------


class TestAttributionReport:
    @pytest.mark.asyncio
    async def test_report_with_stats(self) -> None:
        """Should return formatted attribution report."""
        store = MagicMock()
        store.get_attribution_stats = AsyncMock(
            return_value={"total": 100, "validated": 60, "invalidated": 30, "pending": 10}
        )

        service = KOLAttributionService(kol_store=store)
        report = await service.get_attribution_report()

        assert report["total_calls"] == 100
        assert report["validated"] == 60
        assert report["invalidated"] == 30
        assert report["pending"] == 10
        assert report["accuracy_pct"] == 60.0

    @pytest.mark.asyncio
    async def test_report_with_source_filter(self) -> None:
        """Should include source details when filtering by source_id."""
        store = MagicMock()
        store.get_attribution_stats = AsyncMock(
            return_value={"total": 50, "validated": 30, "invalidated": 15, "pending": 5}
        )
        store.get_source = AsyncMock(
            return_value=MockKOLSource(
                id=1, name="test_kol", platform="x", handle="testuser",
                reliability_score=0.75, total_calls=50, successful_calls=30,
            )
        )

        service = KOLAttributionService(kol_store=store)
        report = await service.get_attribution_report(source_id=1)

        assert report["accuracy_pct"] == 60.0
        assert "source" in report
        assert report["source"]["name"] == "test_kol"
        assert report["source"]["reliability_score"] == 0.75

    @pytest.mark.asyncio
    async def test_report_zero_total(self) -> None:
        """Should handle zero total calls without division error."""
        store = MagicMock()
        store.get_attribution_stats = AsyncMock(
            return_value={"total": 0, "validated": 0, "invalidated": 0, "pending": 0}
        )

        service = KOLAttributionService(kol_store=store)
        report = await service.get_attribution_report()

        assert report["accuracy_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_report_store_failure(self) -> None:
        """Should return empty report on store failure."""
        store = MagicMock()
        store.get_attribution_stats = AsyncMock(side_effect=RuntimeError("DB down"))

        service = KOLAttributionService(kol_store=store)
        report = await service.get_attribution_report()

        assert report["total"] == 0
