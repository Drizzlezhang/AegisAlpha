"""Reddit options/trading subreddit monitor for KOL signals.

Monitors r/options and r/wallstreetbets with quality filtering.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult
from aegis.utils.settings import settings


class RedditTool(BaseTool):
    """Monitor Reddit options/trading subreddits for KOL signals.

    Target subreddits: r/options, r/wallstreetbets (filtered).
    Auth: Reddit OAuth2 client_credentials (REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET).

    Filtering:
    - r/wallstreetbets: DD (Due Diligence) flair only
    - r/options: all posts
    - Last 7 days only
    - upvote_ratio > 0.7 (quality filter)
    """

    name = "reddit_fetch"

    SUBREDDIT_CONFIG: dict[str, dict[str, Any]] = {
        "options": {"flair_filter": None, "min_score": 10},
        "wallstreetbets": {"flair_filter": "DD", "min_score": 50},
    }

    async def fetch(
        self,
        subreddits: list[str] | None = None,
        tickers: list[str] | None = None,
        days_back: int = 7,
        **kwargs: Any,
    ) -> ToolResult:
        """Fetch Reddit trading-related posts.

        Args:
            subreddits: Subreddits to monitor, default ["options", "wallstreetbets"].
            tickers: Ticker symbols to filter for.
            days_back: Lookback window in days.

        Returns:
            ToolResult with data list of {author, ticker, content, url, score,
            created_at, subreddit, source}.
        """
        if subreddits is None:
            subreddits = ["options", "wallstreetbets"]

        access_token = await self._get_reddit_token()
        if not access_token:
            logger.debug("RedditTool: no access token, returning empty")
            return ToolResult(success=True, data=[], source=self.name)

        results: list[dict[str, Any]] = []
        cutoff = datetime.now(UTC) - timedelta(days=days_back)
        ticker_pattern = re.compile(r"\$([A-Z]{1,5})\b")

        async with httpx.AsyncClient(timeout=20) as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "Aegis/1.0",
            }

            for sub in subreddits:
                config = self.SUBREDDIT_CONFIG.get(
                    sub, {"flair_filter": None, "min_score": 10}
                )

                try:
                    resp = await client.get(
                        f"https://oauth.reddit.com/r/{sub}/new.json",
                        headers=headers,
                        params={"limit": 50},
                    )
                    resp.raise_for_status()
                    posts = resp.json().get("data", {}).get("children", [])
                except Exception:
                    logger.debug("RedditTool: fetch failed for sub=%s", sub)
                    continue

                for post in posts:
                    data = post["data"]

                    # Time filter
                    created = datetime.fromtimestamp(
                        data["created_utc"], tz=UTC
                    )
                    if created < cutoff:
                        continue

                    # Quality filter
                    if data.get("score", 0) < config["min_score"]:
                        continue
                    if data.get("upvote_ratio", 0) < 0.7:
                        continue

                    # Flair filter
                    if config["flair_filter"]:
                        flair = data.get("link_flair_text", "")
                        if config["flair_filter"].lower() not in flair.lower():
                            continue

                    # Extract tickers
                    text = (
                        f"{data.get('title', '')} {data.get('selftext', '')[:500]}"
                    )
                    found_tickers = ticker_pattern.findall(text)

                    if tickers:
                        found_tickers = [t for t in found_tickers if t in tickers]

                    for ticker in found_tickers:
                        results.append({
                            "author": data.get("author", ""),
                            "ticker": ticker,
                            "content": text[:500],
                            "url": f"https://reddit.com{data.get('permalink', '')}",
                            "score": data.get("score", 0),
                            "created_at": created.isoformat(),
                            "subreddit": sub,
                            "source": "reddit",
                        })

        logger.info("RedditTool: found %d results", len(results))
        return ToolResult(success=True, data=results, source=self.name)

    async def _get_reddit_token(self) -> str | None:
        """OAuth2 Client Credentials grant for Reddit API access."""
        client_id = settings.REDDIT_CLIENT_ID
        client_secret = settings.REDDIT_CLIENT_SECRET
        if not client_id or not client_secret:
            return None

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://www.reddit.com/api/v1/access_token",
                    auth=(client_id, client_secret),
                    data={"grant_type": "client_credentials"},
                    headers={"User-Agent": "Aegis/1.0"},
                )
                if resp.status_code == 200:
                    return resp.json().get("access_token")  # type: ignore[no-any-return]
        except Exception:
            logger.debug("RedditTool: OAuth token request failed")

        return None
