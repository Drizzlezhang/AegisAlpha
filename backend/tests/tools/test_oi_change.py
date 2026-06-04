"""Test OIChangeAdapter with mocked httpx responses."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.options_flow.oi_change_adapter import OIChangeAdapter


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


class TestOIChangeAdapter:
    @pytest.fixture
    def adapter(self) -> OIChangeAdapter:
        return OIChangeAdapter()

    @pytest.mark.asyncio
    async def test_fetch_missing_api_key(self, adapter: OIChangeAdapter) -> None:
        with patch.dict("os.environ", {}, clear=True):
            result = await adapter.fetch(ticker="QQQ")
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_fetch_missing_ticker(self, adapter: OIChangeAdapter) -> None:
        with patch.dict("os.environ", {"BARCHART_API_KEY": "test-key"}):
            result = await adapter.fetch()
        assert result.success is False
        assert "ticker" in result.error

    @pytest.mark.asyncio
    async def test_fetch_success(self, adapter: OIChangeAdapter) -> None:
        response = _make_mock_response(
            200,
            {
                "call_oi_delta": 1500,
                "put_oi_delta": -800,
                "oi_delta": 3.5,
                "daily_oi": [
                    {"date": "2026-06-04", "call_oi": 50000, "put_oi": 45000},
                    {"date": "2026-06-03", "call_oi": 48500, "put_oi": 45800},
                ],
            },
        )
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"BARCHART_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(ticker="QQQ")

        assert result.success is True
        assert result.source == "oi_change"
        assert result.data["call_oi_delta"] == 1500
        assert result.data["put_oi_delta"] == -800
        assert result.data["oi_delta"] == 3.5
        assert len(result.data["daily_oi"]) == 2

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, adapter: OIChangeAdapter) -> None:
        response = _make_mock_response(500, {})
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"BARCHART_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(ticker="QQQ")

        assert result.success is False
        assert "HTTP 500" in result.error

    @pytest.mark.asyncio
    async def test_fetch_zero_oi_delta(self, adapter: OIChangeAdapter) -> None:
        response = _make_mock_response(
            200,
            {
                "call_oi_delta": 0,
                "put_oi_delta": 0,
                "oi_delta": 0,
                "daily_oi": [],
            },
        )
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"BARCHART_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(ticker="QQQ")

        assert result.success is True
        assert result.data["oi_delta"] == 0
