"""OI Change adapter — 5-day open interest delta from Barchart API."""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult


class OIChangeAdapter(BaseTool):
    """Adapter for Barchart OI Change API — 5-day open interest delta.

    Returns call/put OI changes and daily OI history for a given ticker.
    """

    name = "oi_change"
    BASE_URL = "https://api.barchart.com/api/options/oi"

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
                    f"OIChange HTTP {response.status_code} for {ticker}"
                )
                return ToolResult(
                    success=False,
                    error=f"HTTP {response.status_code}",
                    source=self.name,
                )

            data = response.json()

            # Normalize response into expected structure
            result: dict[str, Any] = {
                "ticker": str(ticker).upper(),
                "call_oi_delta": data.get("call_oi_delta", 0),
                "put_oi_delta": data.get("put_oi_delta", 0),
                "oi_delta": data.get("oi_delta", 0),
                "daily_oi": data.get("daily_oi", []),
            }

            logger.info(
                f"OIChange: {ticker} call_delta={result['call_oi_delta']}, "
                f"put_delta={result['put_oi_delta']}"
            )
            return ToolResult(success=True, data=result, source=self.name)

        except httpx.TimeoutException:
            return ToolResult(
                success=False, error="Request timeout", source=self.name
            )
        except Exception as e:
            logger.warning(f"OIChange fetch failed for {ticker}: {e}")
            return ToolResult(success=False, error=str(e), source=self.name)
