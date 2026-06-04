"""Test TavilyAdapter with mocked httpx responses."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.news.tavily_adapter import TavilyAdapter


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


class TestTavilyAdapter:
    @pytest.fixture
    def adapter(self) -> TavilyAdapter:
        return TavilyAdapter()

    @pytest.mark.asyncio
    async def test_fetch_missing_api_key(self, adapter: TavilyAdapter) -> None:
        """Should return error when API key is not configured."""
        with patch.dict("os.environ", {}, clear=True):
            result = await adapter.fetch(query="QQQ earnings")
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_fetch_missing_query(self, adapter: TavilyAdapter) -> None:
        """Should return error when query is missing."""
        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):
            result = await adapter.fetch()
        assert result.success is False
        assert "query is required" in result.error

    @pytest.mark.asyncio
    async def test_fetch_success(self, adapter: TavilyAdapter) -> None:
        """Should return search results on success."""
        response = _make_mock_response(
            200,
            {
                "results": [
                    {
                        "title": "QQQ Earnings",
                        "url": "https://example.com",
                        "content": "...",
                        "score": 0.9,
                    },
                ]
            },
        )
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(query="QQQ earnings forecast 2026")

        assert result.success is True
        assert result.source == "tavily"
        assert len(result.data) == 1
        assert result.data[0]["title"] == "QQQ Earnings"

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, adapter: TavilyAdapter) -> None:
        """Should return error on non-200 response."""
        response = _make_mock_response(500, {})
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(query="QQQ")

        assert result.success is False
        assert "HTTP 500" in result.error

    @pytest.mark.asyncio
    async def test_fetch_appends_stock_market_context(self, adapter: TavilyAdapter) -> None:
        """Query without stock/market keywords should get context appended."""
        response = _make_mock_response(200, {"results": []})
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(query="QQQ forecast")

        assert result.success is True
        # Verify the query was modified — check the mock was called with stock market context
        call_args = mock_client.post.call_args
        assert call_args is not None
        sent_query = call_args[1]["json"]["query"]
        assert "stock market" in sent_query
