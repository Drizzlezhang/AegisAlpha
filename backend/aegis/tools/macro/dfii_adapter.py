"""DFII adapter — 10-Year TIPS Real Interest Rate from FRED (DFII10)."""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult


class DFIIAdapter(BaseTool):
    """Adapter for FRED DFII10 (10-Year Treasury Inflation-Indexed Security).

    DFII10 is a key macro indicator:
    - Rising real rates → headwind for gold (GLD) and growth stocks
    - Falling real rates → tailwind for gold and growth stocks
    """

    name = "dfii"
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def _get_api_key(self) -> str | None:
        return os.getenv("FRED_API_KEY")

    async def fetch(self, **kwargs: Any) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="FRED_API_KEY not configured in .env",
                source=self.name,
            )

        params: dict[str, str] = {
            "series_id": "DFII10",
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": "30",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)

            if response.status_code != 200:
                logger.warning(f"DFII HTTP {response.status_code}")
                return ToolResult(
                    success=False,
                    error=f"HTTP {response.status_code}",
                    source=self.name,
                )

            data = response.json()
            if "error_code" in data:
                return ToolResult(
                    success=False,
                    error=data.get("error_message", "FRED API error"),
                    source=self.name,
                )

            observations = data.get("observations", [])
            if observations:
                latest = observations[0]
                dfii10 = float(latest["value"]) if latest["value"] != "." else None
                logger.info(f"DFII10: {dfii10}% on {latest['date']}")
                return ToolResult(
                    success=True,
                    data={
                        "dfii10": dfii10,
                        "date": latest["date"],
                        "series_id": "DFII10",
                    },
                    source=self.name,
                )

            return ToolResult(
                success=False,
                error="No observations returned",
                source=self.name,
            )

        except httpx.TimeoutException:
            return ToolResult(success=False, error="Request timeout", source=self.name)
        except Exception as e:
            logger.warning(f"DFII fetch failed: {e}")
            return ToolResult(success=False, error=str(e), source=self.name)
