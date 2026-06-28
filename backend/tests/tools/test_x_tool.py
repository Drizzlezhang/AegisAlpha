"""Tests for XSearchTool — Tavily-based X/Twitter KOL search."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.social.x_tool import XSearchTool


def _make_mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def _mock_async_client(response: MagicMock) -> MagicMock:
    mock_post = AsyncMock(return_value=response)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = mock_post
    return mock_client


class TestXSearchTool:
    @pytest.fixture
    def tool(self) -> XSearchTool:
        return XSearchTool()

    @pytest.mark.asyncio
    async def test_fetch_no_api_key(self, tool: XSearchTool) -> None:
        """Should return empty data when TAVILY_API_KEY is not configured."""
        with patch("aegis.tools.social.x_tool.settings") as mock_settings:
            mock_settings.TAVILY_API_KEY = ""
            result = await tool.fetch(
                kol_handles=["testuser"], tickers=["QQQ"]
            )
        assert result.success is True
        assert result.data == []

    @pytest.mark.asyncio
    async def test_fetch_empty_handles(self, tool: XSearchTool) -> None:
        """Should return empty data when no handles provided."""
        result = await tool.fetch(kol_handles=[], tickers=["QQQ"])
        assert result.success is True
        assert result.data == []

    @pytest.mark.asyncio
    async def test_fetch_success(self, tool: XSearchTool) -> None:
        """Should return search results on success."""
        response = _make_mock_response(
            200,
            {
                "results": [
                    {
                        "content": "QQQ looks bullish here",
                        "url": "https://x.com/testuser/status/123",
                        "published_date": "2026-06-20",
                    },
                ]
            },
        )
        mock_client = _mock_async_client(response)

        with (
            patch("aegis.tools.social.x_tool.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            mock_settings.TAVILY_API_KEY = "test-key"
            result = await tool.fetch(
                kol_handles=["testuser"], tickers=["QQQ"]
            )

        assert result.success is True
        assert result.source == "x_search"
        assert len(result.data) == 1
        assert result.data[0]["handle"] == "testuser"
        assert result.data[0]["ticker"] == "QQQ"
        assert result.data[0]["source"] == "x"
        assert "bullish" in result.data[0]["content"]

    @pytest.mark.asyncio
    async def test_fetch_single_failure_not_fatal(self, tool: XSearchTool) -> None:
        """Single handle/ticker failure should not abort the whole fetch."""
        fail_response = _make_mock_response(500, {})
        success_response = _make_mock_response(
            200,
            {
                "results": [
                    {
                        "content": "SPY analysis",
                        "url": "https://x.com/user2/status/456",
                        "published_date": "2026-06-21",
                    },
                ]
            },
        )

        call_count = 0

        async def side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fail_response
            return success_response

        mock_post = AsyncMock(side_effect=side_effect)
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = mock_post

        with (
            patch("aegis.tools.social.x_tool.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            mock_settings.TAVILY_API_KEY = "test-key"
            result = await tool.fetch(
                kol_handles=["user1", "user2"], tickers=["QQQ"]
            )

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["handle"] == "user2"

    @pytest.mark.asyncio
    async def test_fetch_multiple_handles_tickers(self, tool: XSearchTool) -> None:
        """Should iterate over all handle × ticker combinations."""
        response = _make_mock_response(
            200,
            {
                "results": [
                    {
                        "content": "test",
                        "url": "https://x.com/h/status/1",
                        "published_date": "2026-06-20",
                    },
                ]
            },
        )
        mock_client = _mock_async_client(response)

        with (
            patch("aegis.tools.social.x_tool.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            mock_settings.TAVILY_API_KEY = "test-key"
            result = await tool.fetch(
                kol_handles=["h1", "h2"], tickers=["QQQ", "SPY"]
            )

        assert result.success is True
        # 2 handles × 2 tickers × 1 result each = 4
        assert len(result.data) == 4
