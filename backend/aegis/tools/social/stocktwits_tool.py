"""StockTwits API integration for KOL signal collection.

Fetches user streams from StockTwits and extracts sentiment signals.
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult
from aegis.utils.settings import settings


class StockTwitsTool(BaseTool):
    """Fetch recent posts from StockTwits KOL accounts.

    API: GET https://api.stocktwits.com/api/2/streams/user/{handle}.json
    Auth: Bearer token (STOCKTWITS_ACCESS_TOKEN), optional.

    Each user stream returns up to 30 messages with:
    - sentiment (bullish / bearish / null)
    - symbols (mentioned tickers)
    - body (message text)
    """

    name = "stocktwits_fetch"

    async def fetch(
        self,
        handles: list[str] | None = None,
        target_tickers: list[str] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Fetch StockTwits user streams.

        Args:
            handles: StockTwits usernames.
            target_tickers: If set, only return posts mentioning these tickers.

        Returns:
            ToolResult with data list of {handle, ticker, content, sentiment,
            url, created_at, source}.
        """
        if not handles:
            handles = []

        results: list[dict[str, Any]] = []
        token = settings.STOCKTWITS_ACCESS_TOKEN

        async with httpx.AsyncClient(timeout=20) as client:
            for handle in handles:
                try:
                    headers: dict[str, str] = {}
                    if token:
                        headers["Authorization"] = f"Bearer {token}"

                    resp = await client.get(
                        f"https://api.stocktwits.com/api/2/streams/user/{handle}.json",
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    for msg in data.get("messages", []):
                        symbols = [s["symbol"] for s in msg.get("symbols", [])]

                        # Filter by target tickers
                        if target_tickers:
                            matched = [s for s in symbols if s in target_tickers]
                            if not matched:
                                continue
                        else:
                            matched = symbols

                        sentiment = None
                        if msg.get("entities", {}).get("sentiment"):
                            sentiment = msg["entities"]["sentiment"].get("basic")

                        for ticker in matched:
                            results.append({
                                "handle": handle,
                                "ticker": ticker,
                                "content": msg.get("body", ""),
                                "sentiment": sentiment,
                                "url": (
                                    f"https://stocktwits.com/{handle}/message/{msg['id']}"
                                ),
                                "created_at": msg.get("created_at", ""),
                                "source": "stocktwits",
                            })
                except Exception:
                    logger.debug(
                        "StockTwitsTool: fetch failed for handle=%s", handle
                    )
                    continue

        logger.info("StockTwitsTool: found %d results", len(results))
        return ToolResult(success=True, data=results, source=self.name)
