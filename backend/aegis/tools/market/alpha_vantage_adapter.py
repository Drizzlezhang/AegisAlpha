"""Alpha Vantage adapter — market data fallback, earnings calendar, company overview."""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult


class AlphaVantageAdapter(BaseTool):
    """Adapter for Alpha Vantage API.

    Supports:
    - TIME_SERIES_DAILY: daily OHLCV
    - EARNINGS_CALENDAR: upcoming earnings
    - OVERVIEW: company fundamentals
    """

    name = "alpha_vantage"
    BASE_URL = "https://www.alphavantage.co/query"

    def _get_api_key(self) -> str | None:
        return os.getenv("ALPHA_VANTAGE_API_KEY")

    async def fetch(self, **kwargs: Any) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="ALPHA_VANTAGE_API_KEY not configured in .env",
                source=self.name,
            )

        ticker = kwargs.get("ticker", "")
        function = kwargs.get("function", "TIME_SERIES_DAILY")

        if not ticker:
            return ToolResult(success=False, error="ticker is required", source=self.name)

        params: dict[str, str] = {
            "function": function,
            "symbol": ticker,
            "apikey": api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)

            if response.status_code != 200:
                logger.warning(f"Alpha Vantage HTTP {response.status_code} for {ticker}")
                return ToolResult(
                    success=False,
                    error=f"HTTP {response.status_code}",
                    source=self.name,
                )

            data = response.json()

            # Check for API error messages
            if "Error Message" in data:
                return ToolResult(
                    success=False,
                    error=data["Error Message"],
                    source=self.name,
                )
            if "Note" in data:
                logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                return ToolResult(
                    success=False,
                    error="API rate limit reached",
                    source=self.name,
                )

            logger.info(f"Alpha Vantage {function}: {ticker}")
            return ToolResult(success=True, data=data, source=self.name)

        except httpx.TimeoutException:
            return ToolResult(success=False, error="Request timeout", source=self.name)
        except Exception as e:
            logger.warning(f"Alpha Vantage fetch failed for {ticker}: {e}")
            return ToolResult(success=False, error=str(e), source=self.name)
