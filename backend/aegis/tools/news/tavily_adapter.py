"""Tavily adapter — semantic news search."""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult


class TavilyAdapter(BaseTool):
    """Adapter for Tavily semantic search API.

    Returns news articles and web content relevant to the query.
    """

    name = "tavily"
    BASE_URL = "https://api.tavily.com/search"

    def _get_api_key(self) -> str | None:
        return os.getenv("TAVILY_API_KEY")

    async def fetch(self, **kwargs: Any) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="TAVILY_API_KEY not configured in .env",
                source=self.name,
            )

        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)

        if not query:
            return ToolResult(success=False, error="query is required", source=self.name)

        # Append stock market context for better results
        if "stock" not in query.lower() and "market" not in query.lower():
            query = f"{query} stock market"

        payload: dict[str, Any] = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.BASE_URL, json=payload)

            if response.status_code != 200:
                logger.warning(f"Tavily HTTP {response.status_code} for query: {query}")
                return ToolResult(
                    success=False,
                    error=f"HTTP {response.status_code}",
                    source=self.name,
                )

            data = response.json()
            results = data.get("results", [])

            logger.info(f"Tavily search: {len(results)} results for '{query}'")
            return ToolResult(success=True, data=results, source=self.name)

        except httpx.TimeoutException:
            return ToolResult(success=False, error="Request timeout", source=self.name)
        except Exception as e:
            logger.warning(f"Tavily fetch failed: {e}")
            return ToolResult(success=False, error=str(e), source=self.name)
