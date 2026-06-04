"""Barchart Options adapter — CBOE options data including IV rank/percentile."""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult


class BarchartOptionsAdapter(BaseTool):
    """Adapter for Barchart Options API — CBOE options data.

    Returns IV rank, IV percentile, call/put volume for a given ticker.
    """

    name = "barchart_options"
    BASE_URL = "https://api.barchart.com/api/options/data"

    def _get_api_key(self) -> str | None:
        return os.getenv("BARCHART_API_KEY")

    async def fetch(self, **kwargs: Any) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="BARCHART_API_KEY not configured in .env",
                source=self.name,
            )

        ticker = kwargs.get("ticker")
        if not ticker:
            return ToolResult(
                success=False,
                error="ticker is required",
                source=self.name,
            )

        params: dict[str, str] = {
            "symbol": str(ticker).upper(),
            "apikey": api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)

            if response.status_code != 200:
                logger.warning(
                    f"BarchartOptions HTTP {response.status_code} for {ticker}"
                )
                return ToolResult(
                    success=False,
                    error=f"HTTP {response.status_code}",
                    source=self.name,
                )

            data = response.json()

            result: dict[str, Any] = {
                "ticker": str(ticker).upper(),
                "iv_rank": data.get("iv_rank", 0),
                "iv_percentile": data.get("iv_percentile", 0),
                "call_volume": data.get("call_volume", 0),
                "put_volume": data.get("put_volume", 0),
            }

            logger.info(
                f"BarchartOptions: {ticker} iv_rank={result['iv_rank']}, "
                f"iv_percentile={result['iv_percentile']}"
            )
            return ToolResult(success=True, data=result, source=self.name)

        except httpx.TimeoutException:
            return ToolResult(
                success=False, error="Request timeout", source=self.name
            )
        except Exception as e:
            logger.warning(f"BarchartOptions fetch failed for {ticker}: {e}")
            return ToolResult(success=False, error=str(e), source=self.name)
