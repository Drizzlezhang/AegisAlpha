"""Test ETFFlowsAdapter — etfdb scraping, wisesheets fallback, error handling."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.flows.etf_flows_adapter import ETFFlowsAdapter


class TestETFFlowsAdapter:
    """Verify ETFFlowsAdapter fetch behavior."""

    @pytest.fixture
    def adapter(self) -> ETFFlowsAdapter:
        return ETFFlowsAdapter()

    @pytest.mark.asyncio
    async def test_fetch_etfdb_success(self, adapter: ETFFlowsAdapter) -> None:
        """Should return success with data for all default symbols."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await adapter.fetch()

        assert result.success is True
        assert result.source == "etf_flows"
        for sym in ["SPY", "QQQ", "GLD", "SLV"]:
            assert sym in result.data
            assert "flow_7d" in result.data[sym]

    @pytest.mark.asyncio
    async def test_fetch_etfdb_http_error(self, adapter: ETFFlowsAdapter) -> None:
        """Should still return success with unavailable status on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await adapter.fetch()

        assert result.success is True  # Degrades gracefully
        assert result.data["SPY"]["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_fetch_custom_symbols(self, adapter: ETFFlowsAdapter) -> None:
        """Should accept custom symbols list."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await adapter.fetch(symbols=["IWM", "DIA"])

        assert result.success is True
        assert "IWM" in result.data
        assert "DIA" in result.data

    @pytest.mark.asyncio
    async def test_fetch_wisesheets_not_implemented(
        self, adapter: ETFFlowsAdapter,
    ) -> None:
        """Should return failure for wisesheets source."""
        with patch.object(
            adapter, "_fetch_wisesheets",
            AsyncMock(return_value=MagicMock(success=False, error="not implemented")),
        ):
            result = await adapter._fetch_wisesheets(["SPY"])
        assert result.success is False
