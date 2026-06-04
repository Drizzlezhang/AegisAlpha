"""Finviz Screener adapter — stock screener and filter queries."""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult


class FinvizScreenerAdapter(BaseTool):
    """Adapter for Finviz Screener API — stock screening and filtering.

    Returns screener results matching the provided filter criteria.
    """

    name = "finviz"
    BASE_URL = "https://api.finviz.com/api/screener"

    def _get_api_key(self) -> str | None:
        return os.getenv("FINVIZ_API_KEY")

    async def fetch(self, **kwargs: Any) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="FINVIZ_API_KEY not configured in .env",
                source=self.name,
            )

        filters = kwargs.get("filters", kwargs.get("filter", ""))
        params: dict[str, str] = {
            "apikey": api_key,
        }
        if filters:
            params["f"] = str(filters)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)

            if response.status_code != 200:
                logger.warning(
                    f"Finviz HTTP {response.status_code}"
                )
                return ToolResult(
                    success=False,
                    error=f"HTTP {response.status_code}",
                    source=self.name,
                )

            data = response.json()
            results: list[dict[str, Any]] = data.get("data", data.get("results", []))

            logger.info(f"Finviz: {len(results)} results")
            return ToolResult(success=True, data=results, source=self.name)

        except httpx.TimeoutException:
            return ToolResult(
                success=False, error="Request timeout", source=self.name
            )
        except Exception as e:
            logger.warning(f"Finviz fetch failed: {e}")
            return ToolResult(success=False, error=str(e), source=self.name)
