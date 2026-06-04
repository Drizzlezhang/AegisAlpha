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
            {
                "Open": [450.0],
                "High": [455.0],
                "Low": [448.0],
                "Close": [453.0],
                "Volume": [35000000],
            }
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

    @pytest.mark.asyncio
    async def test_fetch_options_chain_success(self, adapter: YFinanceAdapter) -> None:
        """Should return options chain data with calls and puts."""
        mock_call_df = pd.DataFrame(
            {
                "strike": [450.0, 460.0],
                "lastPrice": [22.5, 17.5],
                "bid": [22.0, 17.0],
                "ask": [23.0, 18.0],
                "volume": [100, 80],
                "openInterest": [500, 400],
                "impliedVolatility": [0.22, 0.21],
            }
        )
        mock_put_df = pd.DataFrame(
            {
                "strike": [450.0, 460.0],
                "lastPrice": [18.0, 24.0],
                "bid": [17.5, 23.5],
                "ask": [18.5, 24.5],
                "volume": [90, 70],
                "openInterest": [450, 350],
                "impliedVolatility": [0.22, 0.21],
            }
        )
        mock_chain = MagicMock()
        mock_chain.calls = mock_call_df
        mock_chain.puts = mock_put_df

        mock_ticker = MagicMock()
        mock_ticker.options = ["2026-07-18", "2026-08-15"]
        mock_ticker.option_chain.return_value = mock_chain

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await adapter.fetch(ticker="QQQ", method="options_chain")

        assert result.success is True
        assert result.source == "yfinance"
        assert len(result.data["chains"]) == 2
        assert result.data["chains"][0]["expiration"] == "2026-07-18"
        assert len(result.data["chains"][0]["calls"]) == 2

    @pytest.mark.asyncio
    async def test_fetch_options_chain_empty(self, adapter: YFinanceAdapter) -> None:
        """Should return error when no options chain available."""
        mock_ticker = MagicMock()
        mock_ticker.options = []

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await adapter.fetch(ticker="QQQ", method="options_chain")

        assert result.success is False
        assert "No options chain" in result.error

    @pytest.mark.asyncio
    async def test_fetch_fundamentals_success(self, adapter: YFinanceAdapter) -> None:
        """Should return fundamentals data."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "marketCap": 200000000000,
            "trailingPE": 25.5,
            "forwardPE": 22.3,
            "priceToBook": 8.2,
            "dividendYield": 0.005,
            "sector": "Technology",
            "industry": "Software",
            "beta": 1.15,
            "fiftyTwoWeekHigh": 500.0,
            "fiftyTwoWeekLow": 350.0,
        }

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await adapter.fetch(ticker="QQQ", method="fundamentals")

        assert result.success is True
        assert result.source == "yfinance"
        assert result.data["market_cap"] == 200000000000
        assert result.data["pe_ratio"] == 25.5
        assert result.data["sector"] == "Technology"
        assert result.data["beta"] == 1.15
