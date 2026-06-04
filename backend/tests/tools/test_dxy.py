"""Test DXYAdapter — US Dollar Index from FRED."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.macro.dxy_adapter import DXYAdapter


class TestDXYAdapter:
    """Verify DXYAdapter fetch behavior."""

    @pytest.fixture
    def adapter(self) -> DXYAdapter:
        return DXYAdapter()

    @pytest.mark.asyncio
    async def test_fetch_success(self, adapter: DXYAdapter) -> None:
        """Should return DXY value."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "observations": [
                {"date": "2026-06-03", "value": "104.52"},
                {"date": "2026-06-02", "value": "104.30"},
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
        assert result.data["dxy"] == 104.52
        assert result.data["series_id"] == "DTWEXBGS"

    @pytest.mark.asyncio
    async def test_fetch_missing_api_key(self, adapter: DXYAdapter) -> None:
        """Should fail when FRED_API_KEY is not set."""
        with patch.dict("os.environ", {}, clear=True):
            result = await adapter.fetch()

        assert result.success is False
        assert "FRED_API_KEY" in (result.error or "")

    @pytest.mark.asyncio
    async def test_fetch_no_observations(self, adapter: DXYAdapter) -> None:
        """Should fail when no observations returned."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"observations": []}

        with patch.dict("os.environ", {"FRED_API_KEY": "test_key"}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                result = await adapter.fetch()

        assert result.success is False
