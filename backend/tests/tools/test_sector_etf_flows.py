"""Test SectorETFFlowsAdapter — 10 sector ETF flow data."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.tools.flows.sector_etf_flows_adapter import (
    SECTOR_ETFS,
    SectorETFFlowsAdapter,
)


class TestSectorETFFlowsAdapter:
    """Verify SectorETFFlowsAdapter fetch behavior."""

    @pytest.fixture
    def adapter(self) -> SectorETFFlowsAdapter:
        return SectorETFFlowsAdapter()

    @pytest.mark.asyncio
    async def test_fetch_all_10_sectors(self, adapter: SectorETFFlowsAdapter) -> None:
        """Should return data for all 10 sector ETFs."""
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
        assert result.source == "sector_etf_flows"
        for sym in SECTOR_ETFS:
            assert sym in result.data
            assert "flow_7d" in result.data[sym]

    @pytest.mark.asyncio
    async def test_fetch_partial_failure(self, adapter: SectorETFFlowsAdapter) -> None:
        """Should still return success when some sectors fail."""
        call_count = 0

        async def mock_get(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            # First 3 succeed, rest fail
            resp.status_code = 200 if call_count <= 3 else 503
            return resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=mock_get)
            mock_client_cls.return_value = mock_client

            result = await adapter.fetch()

        assert result.success is True
        # First 3 should be scraped, rest unavailable
        assert result.data["XLK"]["status"] == "scraped_placeholder"
        assert result.data["XLRE"]["status"] == "unavailable"
