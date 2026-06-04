"""Unusual Whales adapter — institutional unusual options flow data."""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult


class UnusualWhalesAdapter(BaseTool):
    """Adapter for Unusual Whales API — institutional unusual options flow.

    Returns premium-weighted unusual options activity for a given ticker.
    Falls back to MarketChameleonAdapter when unavailable.
    """

    name = "unusual_whales"
    BASE_URL = "https://api.unusualwhales.com/api/options/unusual"

    def _get_api_key(self) -> str | None:
        return os.getenv("UNUSUAL_WHALES_API_KEY")

    async def fetch(self, **kwargs: Any) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="UNUSUAL_WHALES_API_KEY not configured in .env",
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
            "ticker": str(ticker).upper(),
            "api_key": api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)

            if response.status_code != 200:
                logger.warning(
                    f"UnusualWhales HTTP {response.status_code} for {ticker}"
                )
                return ToolResult(
                    success=False,
                    error=f"HTTP {response.status_code}",
                    source=self.name,
                )

            data = response.json()
            unusual_options: list[dict[str, Any]] = data.get("data", data.get("options", []))

            logger.info(
                f"UnusualWhales: {ticker} unusual_options={len(unusual_options)}"
            )
            return ToolResult(success=True, data=unusual_options, source=self.name)

        except httpx.TimeoutException:
            return ToolResult(
                success=False, error="Request timeout", source=self.name
            )
        except Exception as e:
            logger.warning(f"UnusualWhales fetch failed for {ticker}: {e}")
            return ToolResult(success=False, error=str(e), source=self.name)
