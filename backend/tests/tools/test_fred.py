"""Test FREDAdapter with mocked httpx responses."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.macro.fred_adapter import FREDAdapter


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


class TestFREDAdapter:
    @pytest.fixture
    def adapter(self) -> FREDAdapter:
        return FREDAdapter()

    @pytest.mark.asyncio
    async def test_fetch_missing_api_key(self, adapter: FREDAdapter) -> None:
        """Should return error when API key is not configured."""
        with patch.dict("os.environ", {}, clear=True):
            result = await adapter.fetch(series_id="FEDFUNDS")
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_fetch_missing_series_id(self, adapter: FREDAdapter) -> None:
        """Should return error when no series_id provided."""
        with patch.dict("os.environ", {"FRED_API_KEY": "test-key"}):
            result = await adapter.fetch()
        assert result.success is False
        assert "series_id" in result.error

    @pytest.mark.asyncio
    async def test_fetch_single_series_success(self, adapter: FREDAdapter) -> None:
        """Should return observations for a single series."""
        response = _make_mock_response(
            200,
            {
                "observations": [
                    {"date": "2024-06-01", "value": "5.33"},
                    {"date": "2024-05-01", "value": "5.33"},
                ],
                "series_id": "FEDFUNDS",
            },
        )
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"FRED_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(series_id="FEDFUNDS")

        assert result.success is True
        assert result.source == "fred"
        assert len(result.data["observations"]) == 2

    @pytest.mark.asyncio
    async def test_fetch_multi_series_success(self, adapter: FREDAdapter) -> None:
        """Should return data for multiple series."""
        response = _make_mock_response(
            200,
            {
                "observations": [{"date": "2024-06-01", "value": "5.33"}],
            },
        )
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"FRED_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(series_ids=["FEDFUNDS", "CPIAUCSL"])

        assert result.success is True
        assert result.source == "fred"
        assert "FEDFUNDS" in result.data
        assert "CPIAUCSL" in result.data

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, adapter: FREDAdapter) -> None:
        """Should return error on non-200 response."""
        response = _make_mock_response(500, {})
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"FRED_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(series_id="FEDFUNDS")

        assert result.success is False
        assert "HTTP 500" in result.error

    @pytest.mark.asyncio
    async def test_fetch_api_error(self, adapter: FREDAdapter) -> None:
        """Should return error when FRED API returns error_code."""
        response = _make_mock_response(
            200,
            {
                "error_code": 400,
                "error_message": "Bad request",
            },
        )
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"FRED_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(series_id="INVALID")

        assert result.success is False
        assert "Bad request" in result.error
