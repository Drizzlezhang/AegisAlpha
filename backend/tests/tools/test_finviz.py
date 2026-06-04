"""Test FinvizScreenerAdapter with mocked httpx responses."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.screener.finviz_adapter import FinvizScreenerAdapter


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


class TestFinvizScreenerAdapter:
    @pytest.fixture
    def adapter(self) -> FinvizScreenerAdapter:
        return FinvizScreenerAdapter()

    @pytest.mark.asyncio
    async def test_fetch_missing_api_key(self, adapter: FinvizScreenerAdapter) -> None:
        with patch.dict("os.environ", {}, clear=True):
            result = await adapter.fetch(filters="cap_large")
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_fetch_success(self, adapter: FinvizScreenerAdapter) -> None:
        response = _make_mock_response(
            200,
            {
                "data": [
                    {"ticker": "AAPL", "price": 195.0, "change": 1.2, "volume": 50000000},
                    {"ticker": "MSFT", "price": 430.0, "change": -0.5, "volume": 30000000},
                ],
            },
        )
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"FINVIZ_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(filters="cap_large")

        assert result.success is True
        assert result.source == "finviz"
        assert len(result.data) == 2
        assert result.data[0]["ticker"] == "AAPL"

    @pytest.mark.asyncio
    async def test_fetch_no_filters(self, adapter: FinvizScreenerAdapter) -> None:
        response = _make_mock_response(200, {"data": []})
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"FINVIZ_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch()

        assert result.success is True
        assert result.data == []

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, adapter: FinvizScreenerAdapter) -> None:
        response = _make_mock_response(429, {})
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"FINVIZ_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(filters="cap_large")

        assert result.success is False
        assert "HTTP 429" in result.error
