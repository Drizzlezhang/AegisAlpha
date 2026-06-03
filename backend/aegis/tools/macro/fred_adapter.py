"""FRED adapter — Federal Reserve Economic Data macro indicators."""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult


class FREDAdapter(BaseTool):
    """Adapter for FRED (Federal Reserve Economic Data) API.

    Supports single and multi-series queries for macro indicators:
    FEDFUNDS, CPIAUCSL, UNRATE, DGS10, VIXCLS, etc.
    """

    name = "fred"
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

        # Support both single series_id and list of series_ids
        series_id = kwargs.get("series_id")
        series_ids = kwargs.get("series_ids")

        if series_ids:
            return await self._fetch_multi(api_key, series_ids)
        elif series_id:
            return await self._fetch_single(api_key, series_id)
        else:
            return ToolResult(
                success=False,
                error="series_id or series_ids is required",
                source=self.name,
            )

    async def _fetch_single(self, api_key: str, series_id: str) -> ToolResult:
        params: dict[str, str] = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": "100",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)

            if response.status_code != 200:
                logger.warning(f"FRED HTTP {response.status_code} for {series_id}")
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

            logger.info(f"FRED: {series_id} observations={len(data.get('observations', []))}")
            return ToolResult(success=True, data=data, source=self.name)

        except httpx.TimeoutException:
            return ToolResult(success=False, error="Request timeout", source=self.name)
        except Exception as e:
            logger.warning(f"FRED fetch failed for {series_id}: {e}")
            return ToolResult(success=False, error=str(e), source=self.name)

    async def _fetch_multi(self, api_key: str, series_ids: list[str]) -> ToolResult:
        results: dict[str, Any] = {}
        errors: list[str] = []

        for sid in series_ids:
            result = await self._fetch_single(api_key, sid)
            if result.success:
                results[sid] = result.data
            else:
                errors.append(f"{sid}: {result.error}")

        if not results:
            return ToolResult(
                success=False,
                error=f"All series failed: {'; '.join(errors)}",
                source=self.name,
            )

        logger.info(f"FRED multi: {len(results)}/{len(series_ids)} series succeeded")
        return ToolResult(success=True, data=results, source=self.name)
