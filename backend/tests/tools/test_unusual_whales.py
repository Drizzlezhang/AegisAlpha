"""Test UnusualWhalesAdapter with mocked httpx responses."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.options_flow.unusual_whales_adapter import UnusualWhalesAdapter


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


class TestUnusualWhalesAdapter:
    @pytest.fixture
    def adapter(self) -> UnusualWhalesAdapter:
        return UnusualWhalesAdapter()

    @pytest.mark.asyncio
    async def test_fetch_missing_api_key(self, adapter: UnusualWhalesAdapter) -> None:
        with patch.dict("os.environ", {}, clear=True):
            result = await adapter.fetch(ticker="QQQ")
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_fetch_missing_ticker(self, adapter: UnusualWhalesAdapter) -> None:
        with patch.dict("os.environ", {"UNUSUAL_WHALES_API_KEY": "test-key"}):
            result = await adapter.fetch()
        assert result.success is False
        assert "ticker" in result.error

    @pytest.mark.asyncio
    async def test_fetch_success(self, adapter: UnusualWhalesAdapter) -> None:
        response = _make_mock_response(
            200,
            {
                "data": [
                    {
                        "type": "call",
                        "strike": 500,
                        "expiration": "2026-07-17",
                        "premium": 250000,
                        "size": 500,
                        "underlying_price": 480,
                        "date": "2026-06-04",
                    },
                    {
                        "type": "put",
                        "strike": 460,
                        "expiration": "2026-07-17",
                        "premium": 180000,
                        "size": 300,
                        "underlying_price": 480,
                        "date": "2026-06-04",
                    },
                ],
            },
        )
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"UNUSUAL_WHALES_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(ticker="QQQ")

        assert result.success is True
        assert result.source == "unusual_whales"
        assert len(result.data) == 2
        assert result.data[0]["type"] == "call"
        assert result.data[1]["type"] == "put"

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, adapter: UnusualWhalesAdapter) -> None:
        response = _make_mock_response(500, {})
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"UNUSUAL_WHALES_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(ticker="QQQ")

        assert result.success is False
        assert "HTTP 500" in result.error

    @pytest.mark.asyncio
    async def test_fetch_empty_data(self, adapter: UnusualWhalesAdapter) -> None:
        response = _make_mock_response(200, {"data": []})
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"UNUSUAL_WHALES_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(ticker="QQQ")

        assert result.success is True
        assert result.data == []
