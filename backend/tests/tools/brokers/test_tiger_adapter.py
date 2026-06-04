"""Tests for TigerAdapter — mock SDK, graceful degradation."""

import pytest

from aegis.tools.brokers.tiger_adapter import TigerAdapter


class TestTigerAdapter:
    """AC-4: TigerAdapter graceful degradation and mock behavior."""

    def test_init_without_sdk(self) -> None:
        adapter = TigerAdapter()
        assert adapter._available is False
        assert adapter._init_error is not None

    def test_get_positions_unavailable(self) -> None:
        adapter = TigerAdapter()
        adapter._available = False
        import asyncio
        result = asyncio.run(adapter.get_positions())
        assert result == []

    def test_get_account_summary_unavailable(self) -> None:
        adapter = TigerAdapter()
        adapter._available = False
        import asyncio
        result = asyncio.run(adapter.get_account_summary())
        assert result == {}

    def test_get_options_chain_unavailable(self) -> None:
        adapter = TigerAdapter()
        adapter._available = False
        import asyncio
        result = asyncio.run(adapter.get_options_chain("QQQ"))
        assert result == []

    def test_get_oi_data_unavailable(self) -> None:
        adapter = TigerAdapter()
        adapter._available = False
        import asyncio
        result = asyncio.run(adapter.get_oi_data("QQQ"))
        assert result == {"ticker": "QQQ", "total_open_interest": 0}
