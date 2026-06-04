"""Tests for FutuAdapter — mock SDK, graceful degradation."""

import pytest

from aegis.tools.brokers.futu_adapter import FutuAdapter


class TestFutuAdapter:
    """AC-2: FutuAdapter graceful degradation and mock behavior."""

    def test_init_without_sdk(self) -> None:
        """Without futu-api installed, adapter should be unavailable."""
        adapter = FutuAdapter()
        assert adapter._available is False
        assert adapter._init_error is not None

    def test_get_positions_unavailable(self) -> None:
        """get_positions should return empty list when unavailable."""
        adapter = FutuAdapter()
        adapter._available = False
        import asyncio
        result = asyncio.run(adapter.get_positions())
        assert result == []

    def test_get_account_summary_unavailable(self) -> None:
        """get_account_summary should return empty dict when unavailable."""
        adapter = FutuAdapter()
        adapter._available = False
        import asyncio
        result = asyncio.run(adapter.get_account_summary())
        assert result == {}

    def test_get_options_chain_unavailable(self) -> None:
        """get_options_chain should return empty list when unavailable."""
        adapter = FutuAdapter()
        adapter._available = False
        import asyncio
        result = asyncio.run(adapter.get_options_chain("QQQ"))
        assert result == []

    def test_get_oi_data_unavailable(self) -> None:
        """get_oi_data should return basic dict when unavailable."""
        adapter = FutuAdapter()
        adapter._available = False
        import asyncio
        result = asyncio.run(adapter.get_oi_data("QQQ"))
        assert result == {"ticker": "QQQ", "total_open_interest": 0, "chain_size": 0}
