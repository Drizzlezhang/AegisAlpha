"""Test HYGLQDSpreadAdapter — credit spread calculation and classification."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from aegis.tools.liquidity.hyg_lqd_spread_adapter import HYGLQDSpreadAdapter


def _make_history(prices: list[float]) -> pd.DataFrame:
    """Create a mock yfinance history DataFrame."""
    idx = pd.date_range("2026-05-28", periods=len(prices), freq="B")
    return pd.DataFrame({"Close": prices}, index=idx)


class TestHYGLQDSpreadAdapter:
    """Verify HYGLQDSpreadAdapter fetch and classification."""

    @pytest.fixture
    def adapter(self) -> HYGLQDSpreadAdapter:
        return HYGLQDSpreadAdapter()

    @pytest.mark.asyncio
    async def test_fetch_risk_on(self, adapter: HYGLQDSpreadAdapter) -> None:
        """HYG outperforming LQD → risk_on."""
        hyg_hist = _make_history([77.0, 77.5, 78.0, 78.5, 79.0])
        lqd_hist = _make_history([108.0, 108.1, 108.0, 107.9, 107.8])

        with patch("yfinance.Ticker") as mock_ticker:
            mock_hyg = MagicMock()
            mock_hyg.history.return_value = hyg_hist
            mock_lqd = MagicMock()
            mock_lqd.history.return_value = lqd_hist
            mock_ticker.side_effect = [mock_hyg, mock_lqd]

            result = await adapter.fetch(period="5d")

        assert result.success is True
        assert result.data["appetite"] == "risk_on"
        assert result.data["current_ratio"] > result.data["ratio_start"]

    @pytest.mark.asyncio
    async def test_fetch_risk_off(self, adapter: HYGLQDSpreadAdapter) -> None:
        """HYG underperforming LQD → risk_off."""
        hyg_hist = _make_history([79.0, 78.5, 78.0, 77.5, 77.0])
        lqd_hist = _make_history([107.8, 107.9, 108.0, 108.1, 108.2])

        with patch("yfinance.Ticker") as mock_ticker:
            mock_hyg = MagicMock()
            mock_hyg.history.return_value = hyg_hist
            mock_lqd = MagicMock()
            mock_lqd.history.return_value = lqd_hist
            mock_ticker.side_effect = [mock_hyg, mock_lqd]

            result = await adapter.fetch(period="5d")

        assert result.success is True
        assert result.data["appetite"] == "risk_off"

    @pytest.mark.asyncio
    async def test_fetch_neutral(self, adapter: HYGLQDSpreadAdapter) -> None:
        """Small change → neutral."""
        hyg_hist = _make_history([77.0, 77.01, 77.02, 77.01, 77.02])
        lqd_hist = _make_history([108.0, 108.01, 108.0, 108.01, 108.0])

        with patch("yfinance.Ticker") as mock_ticker:
            mock_hyg = MagicMock()
            mock_hyg.history.return_value = hyg_hist
            mock_lqd = MagicMock()
            mock_lqd.history.return_value = lqd_hist
            mock_ticker.side_effect = [mock_hyg, mock_lqd]

            result = await adapter.fetch(period="5d")

        assert result.success is True
        assert result.data["appetite"] == "neutral"

    @pytest.mark.asyncio
    async def test_fetch_empty_data(self, adapter: HYGLQDSpreadAdapter) -> None:
        """Empty history → failure."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_hyg = MagicMock()
            mock_hyg.history.return_value = pd.DataFrame()
            mock_lqd = MagicMock()
            mock_lqd.history.return_value = pd.DataFrame()
            mock_ticker.side_effect = [mock_hyg, mock_lqd]

            result = await adapter.fetch()

        assert result.success is False
        assert "No price data" in (result.error or "")
