"""X/Twitter KOL signal collection via Tavily Search API.

Uses Tavily to search for KOL posts on X/Twitter, avoiding the high cost
and rate limits of the native X API.
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult
from aegis.utils.settings import settings


class XSearchTool(BaseTool):
    """Search X/Twitter posts from KOL handles for trading signals via Tavily.

    Search format: "from:@handle $TICKER stock options"
    Returns results from the last N days.
    """

    name = "x_search"

    async def fetch(
        self,
        kol_handles: list[str] | None = None,
        tickers: list[str] | None = None,
        days_back: int = 7,
        **kwargs: Any,
    ) -> ToolResult:
        """Search KOL posts on X/Twitter via Tavily.

        Args:
            kol_handles: KOL X handles (without @).
            tickers: Ticker symbols to search for.
            days_back: Lookback window in days.

        Returns:
            ToolResult with data list of {handle, ticker, content, url,
            published_date, source}.
        """
        if not kol_handles:
            kol_handles = []
        if not tickers:
            tickers = []

        api_key = settings.TAVILY_API_KEY
        if not api_key:
            logger.debug("XSearchTool: TAVILY_API_KEY not configured, returning empty")
            return ToolResult(success=True, data=[], source=self.name)

        results: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for handle in kol_handles:
                for ticker in tickers:
                    query = f"from:@{handle} ${ticker} stock options"
                    try:
                        resp = await client.post(
                            "https://api.tavily.com/search",
                            json={
                                "api_key": api_key,
                                "query": query,
                                "search_depth": "basic",
                                "max_results": 5,
                                "include_domains": ["x.com", "twitter.com"],
                                "days": days_back,
                            },
                        )
                        resp.raise_for_status()
                        data = resp.json()

                        for item in data.get("results", []):
                            results.append({
                                "handle": handle,
                                "ticker": ticker,
                                "content": item.get("content", ""),
                                "url": item.get("url", ""),
                                "published_date": item.get("published_date", ""),
                                "source": "x",
                            })
                    except Exception:
                        logger.debug(
                            "XSearchTool: search failed for handle=%s ticker=%s",
                            handle,
                            ticker,
                        )
                        continue

        logger.info("XSearchTool: found %d results", len(results))
        return ToolResult(success=True, data=results, source=self.name)
