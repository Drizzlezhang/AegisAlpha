"""Test DFIIAdapter — DFII10 real interest rate from FRED."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.macro.dfii_adapter import DFIIAdapter


class TestDFIIAdapter:
    """Verify DFIIAdapter fetch behavior."""

    @pytest.fixture
    def adapter(self) -> DFIIAdapter:
        return DFIIAdapter()

    @pytest.mark.asyncio
    async def test_fetch_success(self, adapter: DFIIAdapter) -> None:
        """Should return DFII10 value."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "observations": [
                {"date": "2026-06-03", "value": "2.15"},
                {"date": "2026-06-02", "value": "2.12"},
            ]
        }

        with patch.dict("os.environ", {"FRED_API_KEY": "test_key"}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                result = await adapter.fetch()

        assert result.success is True
        assert result.data["dfii10"] == 2.15
        assert result.data["series_id"] == "DFII10"

    @pytest.mark.asyncio
    async def test_fetch_missing_api_key(self, adapter: DFIIAdapter) -> None:
        """Should fail when FRED_API_KEY is not set."""
        with patch.dict("os.environ", {}, clear=True):
            result = await adapter.fetch()

        assert result.success is False
        assert "FRED_API_KEY" in (result.error or "")

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, adapter: DFIIAdapter) -> None:
        """Should fail on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.dict("os.environ", {"FRED_API_KEY": "test_key"}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                result = await adapter.fetch()

        assert result.success is False
