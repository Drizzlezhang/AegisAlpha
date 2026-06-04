"""Test AlphaVantageAdapter with mocked httpx responses."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.market.alpha_vantage_adapter import AlphaVantageAdapter


def _make_mock_response(status_code: int, json_data: dict) -> MagicMock:
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def _mock_async_client(response: MagicMock) -> MagicMock:
    """Create a mock httpx.AsyncClient that returns the given response."""
    mock_get = AsyncMock(return_value=response)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = mock_get
    return mock_client


class TestAlphaVantageAdapter:
    @pytest.fixture
    def adapter(self) -> AlphaVantageAdapter:
        return AlphaVantageAdapter()

    @pytest.mark.asyncio
    async def test_fetch_missing_api_key(self, adapter: AlphaVantageAdapter) -> None:
        """Should return error when API key is not configured."""
        with patch.dict("os.environ", {}, clear=True):
            result = await adapter.fetch(ticker="QQQ")
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_fetch_missing_ticker(self, adapter: AlphaVantageAdapter) -> None:
        """Should return error when ticker is missing."""
        with patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"}):
            result = await adapter.fetch()
        assert result.success is False
        assert "ticker is required" in result.error

    @pytest.mark.asyncio
    async def test_fetch_success(self, adapter: AlphaVantageAdapter) -> None:
        """Should return data on successful API call."""
        response = _make_mock_response(
            200,
            {
                "Meta Data": {"1. Information": "Daily Prices"},
                "Time Series (Daily)": {"2024-06-03": {"1. open": "450.0", "4. close": "453.0"}},
            },
        )
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(ticker="QQQ")

        assert result.success is True
        assert result.source == "alpha_vantage"
        assert "Meta Data" in result.data

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, adapter: AlphaVantageAdapter) -> None:
        """Should return error on non-200 response."""
        response = _make_mock_response(429, {})
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(ticker="QQQ")

        assert result.success is False
        assert "HTTP 429" in result.error

    @pytest.mark.asyncio
    async def test_fetch_api_error_message(self, adapter: AlphaVantageAdapter) -> None:
        """Should return error when API returns error message."""
        response = _make_mock_response(200, {"Error Message": "Invalid API call"})
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(ticker="QQQ")

        assert result.success is False
        assert "Invalid API call" in result.error

    @pytest.mark.asyncio
    async def test_fetch_rate_limit_note(self, adapter: AlphaVantageAdapter) -> None:
        """Should return error when API rate limit is hit."""
        response = _make_mock_response(200, {"Note": "API rate limit reached"})
        mock_client = _mock_async_client(response)

        with (
            patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"}),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await adapter.fetch(ticker="QQQ")

        assert result.success is False
        assert "rate limit" in result.error.lower()
