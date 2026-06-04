"""DXY adapter — US Dollar Index from FRED (DTWEXBGS)."""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult


class DXYAdapter(BaseTool):
    """Adapter for FRED DTWEXBGS (Trade Weighted US Dollar Index: Broad).

    DXY is a key cross-asset macro indicator:
    - Strong USD → headwind for commodities (GLD/SLV) and multinationals
    - Weak USD → tailwind for commodities and exporters
    """

    name = "dxy"
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
            "series_id": "DTWEXBGS",
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": "30",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)

            if response.status_code != 200:
                logger.warning(f"DXY HTTP {response.status_code}")
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
                dxy = float(latest["value"]) if latest["value"] != "." else None
                logger.info(f"DXY: {dxy} on {latest['date']}")
                return ToolResult(
                    success=True,
                    data={
                        "dxy": dxy,
                        "date": latest["date"],
                        "series_id": "DTWEXBGS",
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
            logger.warning(f"DXY fetch failed: {e}")
            return ToolResult(success=False, error=str(e), source=self.name)
