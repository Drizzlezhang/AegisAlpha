"""Test YFinanceAdapter with mocked yfinance library."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from aegis.tools.market.yfinance_adapter import YFinanceAdapter


class TestYFinanceAdapter:
    @pytest.fixture
    def adapter(self) -> YFinanceAdapter:
        return YFinanceAdapter()

    @pytest.mark.asyncio
    async def test_fetch_missing_ticker(self, adapter: YFinanceAdapter) -> None:
        """Should return error when ticker is missing."""
        result = await adapter.fetch()
        assert result.success is False
        assert "ticker is required" in result.error

    @pytest.mark.asyncio
    async def test_fetch_history_success(self, adapter: YFinanceAdapter) -> None:
        """Should return OHLCV data on success."""
        mock_df = pd.DataFrame(
            {"Open": [450.0], "High": [455.0], "Low": [448.0], "Close": [453.0], "Volume": [35000000]}
        )
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_df

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await adapter.fetch(ticker="QQQ", period="2y", method="history")

        assert result.success is True
        assert result.source == "yfinance"
        assert isinstance(result.data, pd.DataFrame)

    @pytest.mark.asyncio
    async def test_fetch_history_empty(self, adapter: YFinanceAdapter) -> None:
        """Should return error when no data available."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await adapter.fetch(ticker="INVALID", period="2y", method="history")

        assert result.success is False
        assert "No data" in result.error

    @pytest.mark.asyncio
    async def test_fetch_quote_success(self, adapter: YFinanceAdapter) -> None:
        """Should return quote data on success."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "currentPrice": 453.10,
            "previousClose": 450.00,
            "regularMarketChange": 3.10,
            "regularMarketChangePercent": 0.69,
            "volume": 35000000,
            "marketCap": 200000000000,
        }

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await adapter.fetch(ticker="QQQ", method="quote")

        assert result.success is True
        assert result.source == "yfinance"
        assert result.data["price"] == 453.10
        assert result.data["ticker"] == "QQQ"

    @pytest.mark.asyncio
    async def test_fetch_earnings_date(self, adapter: YFinanceAdapter) -> None:
        """Should return earnings date data."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "earningsDate": "2026-07-15",
            "earningsQuarterlyGrowth": 0.12,
            "revenueGrowth": 0.08,
        }

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await adapter.fetch(ticker="AAPL", method="earnings_date")

        assert result.success is True
        assert result.source == "yfinance"
        assert result.data["next_earnings_date"] == "2026-07-15"

    @pytest.mark.asyncio
    async def test_fetch_unknown_method(self, adapter: YFinanceAdapter) -> None:
        """Should return error for unknown method."""
        result = await adapter.fetch(ticker="QQQ", method="unknown")
        assert result.success is False
        assert "Unknown method" in result.error
