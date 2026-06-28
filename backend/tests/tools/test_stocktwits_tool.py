"""Tests for StockTwitsTool — StockTwits API integration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.social.stocktwits_tool import StockTwitsTool


def _make_mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def _mock_async_client(response: MagicMock) -> MagicMock:
    mock_get = AsyncMock(return_value=response)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = mock_get
    return mock_client


def _stocktwits_message(
    msg_id: int,
    body: str,
    symbols: list[str],
    sentiment: str | None = None,
) -> dict:
    msg: dict = {
        "id": msg_id,
        "body": body,
        "symbols": [{"symbol": s} for s in symbols],
        "created_at": "2026-06-20T10:00:00Z",
    }
    if sentiment:
        msg["entities"] = {"sentiment": {"basic": sentiment}}
    return msg


class TestStockTwitsTool:
    @pytest.fixture
    def tool(self) -> StockTwitsTool:
        return StockTwitsTool()

    @pytest.mark.asyncio
    async def test_fetch_empty_handles(self, tool: StockTwitsTool) -> None:
        """Should return empty data when no handles provided."""
        result = await tool.fetch(handles=[])
        assert result.success is True
        assert result.data == []

    @pytest.mark.asyncio
    async def test_fetch_success_with_sentiment(self, tool: StockTwitsTool) -> None:
        """Should extract sentiment and symbols from StockTwits messages."""
        response = _make_mock_response(
            200,
            {
                "messages": [
                    _stocktwits_message(
                        1, "QQQ to the moon!", ["QQQ"], "Bullish"
                    ),
                ]
            },
        )
        mock_client = _mock_async_client(response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.fetch(handles=["trader1"])

        assert result.success is True
        assert result.source == "stocktwits_fetch"
        assert len(result.data) == 1
        assert result.data[0]["handle"] == "trader1"
        assert result.data[0]["ticker"] == "QQQ"
        assert result.data[0]["sentiment"] == "Bullish"
        assert result.data[0]["source"] == "stocktwits"

    @pytest.mark.asyncio
    async def test_fetch_target_ticker_filter(self, tool: StockTwitsTool) -> None:
        """Should filter messages to only target tickers."""
        response = _make_mock_response(
            200,
            {
                "messages": [
                    _stocktwits_message(1, "QQQ and SPY", ["QQQ", "SPY"]),
                ]
            },
        )
        mock_client = _mock_async_client(response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.fetch(
                handles=["trader1"], target_tickers=["QQQ"]
            )

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["ticker"] == "QQQ"

    @pytest.mark.asyncio
    async def test_fetch_target_ticker_no_match(self, tool: StockTwitsTool) -> None:
        """Should exclude messages with no matching target tickers."""
        response = _make_mock_response(
            200,
            {
                "messages": [
                    _stocktwits_message(1, "SPY only", ["SPY"]),
                ]
            },
        )
        mock_client = _mock_async_client(response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.fetch(
                handles=["trader1"], target_tickers=["QQQ"]
            )

        assert result.success is True
        assert len(result.data) == 0

    @pytest.mark.asyncio
    async def test_fetch_no_sentiment(self, tool: StockTwitsTool) -> None:
        """Should handle messages without sentiment field."""
        response = _make_mock_response(
            200,
            {
                "messages": [
                    _stocktwits_message(1, "Just a thought on QQQ", ["QQQ"]),
                ]
            },
        )
        mock_client = _mock_async_client(response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.fetch(handles=["trader1"])

        assert result.success is True
        assert result.data[0]["sentiment"] is None

    @pytest.mark.asyncio
    async def test_fetch_single_handle_failure(self, tool: StockTwitsTool) -> None:
        """Single handle failure should not abort other handles."""
        fail_response = _make_mock_response(500, {})
        success_response = _make_mock_response(
            200,
            {
                "messages": [
                    _stocktwits_message(1, "QQQ analysis", ["QQQ"]),
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

        mock_get = AsyncMock(side_effect=side_effect)
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = mock_get

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.fetch(handles=["bad_handle", "good_handle"])

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["handle"] == "good_handle"
