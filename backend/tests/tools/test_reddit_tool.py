"""Tests for RedditTool — Reddit subreddit monitor."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.social.reddit_tool import RedditTool

# Use a recent timestamp so posts pass the 7-day cutoff filter
_RECENT_UTC = datetime.now(timezone.utc).timestamp()


def _make_mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def _mock_async_client(get_response: MagicMock) -> MagicMock:
    mock_get = AsyncMock(return_value=get_response)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = mock_get
    return mock_client


def _reddit_post(
    title: str,
    selftext: str,
    author: str = "testuser",
    score: int = 100,
    upvote_ratio: float = 0.9,
    created_utc: float = _RECENT_UTC,
    subreddit: str = "options",
    flair: str = "",
    permalink: str = "/r/options/comments/abc/test/",
) -> dict:
    return {
        "data": {
            "title": title,
            "selftext": selftext,
            "author": author,
            "score": score,
            "upvote_ratio": upvote_ratio,
            "created_utc": created_utc,
            "subreddit": subreddit,
            "link_flair_text": flair,
            "permalink": permalink,
        }
    }


class TestRedditTool:
    @pytest.fixture
    def tool(self) -> RedditTool:
        return RedditTool()

    @pytest.mark.asyncio
    async def test_fetch_no_credentials(self, tool: RedditTool) -> None:
        """Should return empty data when Reddit credentials not configured."""
        with patch.object(
            tool, "_get_reddit_token", AsyncMock(return_value=None)
        ):
            result = await tool.fetch()
        assert result.success is True
        assert result.data == []

    @pytest.mark.asyncio
    async def test_fetch_success(self, tool: RedditTool) -> None:
        """Should fetch and filter Reddit posts with ticker extraction."""
        posts_response = _make_mock_response(
            200,
            {
                "data": {
                    "children": [
                        _reddit_post(
                            title="$QQQ analysis \u2014 bullish setup",
                            selftext="QQQ looks great here with strong momentum",
                            score=50,
                        ),
                    ]
                }
            },
        )
        mock_client = _mock_async_client(posts_response)

        with (
            patch.object(tool, "_get_reddit_token", AsyncMock(return_value="fake-token")),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await tool.fetch(tickers=["QQQ"])

        assert result.success is True
        assert result.source == "reddit_fetch"
        assert len(result.data) == 1
        assert result.data[0]["ticker"] == "QQQ"
        assert result.data[0]["author"] == "testuser"
        assert result.data[0]["source"] == "reddit"
        assert result.data[0]["subreddit"] == "options"

    @pytest.mark.asyncio
    async def test_fetch_quality_filter_score(self, tool: RedditTool) -> None:
        """Should filter out posts below min_score."""
        posts_response = _make_mock_response(
            200,
            {
                "data": {
                    "children": [
                        _reddit_post(title="$QQQ low score", selftext="...", score=5),
                        _reddit_post(title="$QQQ good score", selftext="...", score=50),
                    ]
                }
            },
        )
        mock_client = _mock_async_client(posts_response)

        with (
            patch.object(tool, "_get_reddit_token", AsyncMock(return_value="fake-token")),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await tool.fetch(tickers=["QQQ"])

        assert len(result.data) == 1
        assert result.data[0]["score"] == 50

    @pytest.mark.asyncio
    async def test_fetch_quality_filter_upvote_ratio(self, tool: RedditTool) -> None:
        """Should filter out posts with low upvote_ratio."""
        posts_response = _make_mock_response(
            200,
            {
                "data": {
                    "children": [
                        _reddit_post(title="$QQQ bad ratio", selftext="...", upvote_ratio=0.5),
                    ]
                }
            },
        )
        mock_client = _mock_async_client(posts_response)

        with (
            patch.object(tool, "_get_reddit_token", AsyncMock(return_value="fake-token")),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await tool.fetch(tickers=["QQQ"])

        assert len(result.data) == 0

    @pytest.mark.asyncio
    async def test_fetch_wsb_dd_flair_filter(self, tool: RedditTool) -> None:
        """Should only include DD-flaired posts from wallstreetbets."""
        posts_response = _make_mock_response(
            200,
            {
                "data": {
                    "children": [
                        _reddit_post(
                            title="$QQQ DD analysis",
                            selftext="thorough analysis...",
                            subreddit="wallstreetbets",
                            flair="DD",
                            score=60,
                        ),
                        _reddit_post(
                            title="$QQQ YOLO",
                            selftext="meme post...",
                            subreddit="wallstreetbets",
                            flair="YOLO",
                            score=100,
                        ),
                    ]
                }
            },
        )
        mock_client = _mock_async_client(posts_response)

        with (
            patch.object(tool, "_get_reddit_token", AsyncMock(return_value="fake-token")),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await tool.fetch(subreddits=["wallstreetbets"], tickers=["QQQ"])

        assert len(result.data) == 1
        assert "DD" in result.data[0]["content"]

    @pytest.mark.asyncio
    async def test_fetch_subreddit_failure_not_fatal(self, tool: RedditTool) -> None:
        """One subreddit failing should not abort others."""
        call_count = 0

        async def get_side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_mock_response(500, {})
            return _make_mock_response(
                200,
                {
                    "data": {
                        "children": [
                            _reddit_post(
                                title="$QQQ from wsb",
                                selftext="analysis",
                                score=60,
                                subreddit="wallstreetbets",
                                flair="DD",
                            ),
                        ]
                    }
                },
            )

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=get_side_effect)

        with (
            patch.object(tool, "_get_reddit_token", AsyncMock(return_value="fake-token")),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await tool.fetch(subreddits=["options", "wallstreetbets"], tickers=["QQQ"])

        assert result.success is True
        assert len(result.data) == 1

    @pytest.mark.asyncio
    async def test_fetch_ticker_extraction(self, tool: RedditTool) -> None:
        """Should extract tickers using $TICKER pattern."""
        posts_response = _make_mock_response(
            200,
            {
                "data": {
                    "children": [
                        _reddit_post(
                            title="$QQQ and $SPY analysis",
                            selftext="Comparing $QQQ with $NVDA",
                            score=50,
                        ),
                    ]
                }
            },
        )
        mock_client = _mock_async_client(posts_response)

        with (
            patch.object(tool, "_get_reddit_token", AsyncMock(return_value="fake-token")),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await tool.fetch()

        tickers_found = {r["ticker"] for r in result.data}
        assert "QQQ" in tickers_found
        assert "SPY" in tickers_found
        assert "NVDA" in tickers_found
