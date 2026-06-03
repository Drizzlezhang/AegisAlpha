"""YFinance adapter — OHLCV, quote, and earnings date via yfinance library."""

from __future__ import annotations

from typing import Any

from loguru import logger

from aegis.tools.base import BaseTool, ToolResult


class YFinanceAdapter(BaseTool):
    """Adapter for Yahoo Finance data via yfinance library.

    Supports:
    - history: OHLCV daily/weekly data
    - quote: real-time price snapshot
    - earnings_date: next earnings date
    """

    name = "yfinance"

    async def fetch(self, **kwargs: Any) -> ToolResult:
        ticker = kwargs.get("ticker", "")
        period = kwargs.get("period", "1y")
        method = kwargs.get("method", "history")

        if not ticker:
            return ToolResult(success=False, error="ticker is required", source=self.name)

        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)

            if method == "history":
                data = stock.history(period=period)
                if data.empty:
                    return ToolResult(
                        success=False,
                        error=f"No data for {ticker} period={period}",
                        source=self.name,
                    )
                logger.info(f"yfinance history: {ticker} period={period} rows={len(data)}")
                return ToolResult(success=True, data=data, source=self.name)

            elif method == "quote":
                info = stock.info
                quote_data = {
                    "ticker": ticker,
                    "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                    "previous_close": info.get("previousClose"),
                    "change": info.get("regularMarketChange"),
                    "change_pct": info.get("regularMarketChangePercent"),
                    "volume": info.get("volume"),
                    "market_cap": info.get("marketCap"),
                }
                logger.info(f"yfinance quote: {ticker} price={quote_data['price']}")
                return ToolResult(success=True, data=quote_data, source=self.name)

            elif method == "earnings_date":
                info = stock.info
                earnings_data = {
                    "ticker": ticker,
                    "next_earnings_date": info.get("earningsDate"),
                    "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
                    "revenue_growth": info.get("revenueGrowth"),
                }
                logger.info(f"yfinance earnings_date: {ticker}")
                return ToolResult(success=True, data=earnings_data, source=self.name)

            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown method: {method}. Supported: history, quote, earnings_date",
                    source=self.name,
                )

        except ImportError:
            return ToolResult(
                success=False,
                error="yfinance library not installed. Run: uv add yfinance",
                source=self.name,
            )
        except Exception as e:
            logger.warning(f"yfinance fetch failed for {ticker}: {e}")
            return ToolResult(success=False, error=str(e), source=self.name)
