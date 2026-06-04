"""Test ToolRegistry — loading, get, find_by_tag, fallback, circuit_breaker."""

from unittest.mock import AsyncMock

import pytest

from aegis.tools.base import ToolResult
from aegis.tools.registry import ToolRegistry


class TestToolRegistry:
    @pytest.fixture
    def registry(self) -> ToolRegistry:
        return ToolRegistry.load_from_yaml("config/tools.yaml")

    def test_load_all_tools(self, registry: ToolRegistry) -> None:
        """All 4 tools should be loaded."""
        names = registry.list_all()
        assert "yfinance" in names
        assert "alpha_vantage" in names
        assert "fred" in names
        assert "tavily" in names

    def test_get_existing_tool(self, registry: ToolRegistry) -> None:
        """get() should return a ToolProxy for existing tools."""
        proxy = registry.get("yfinance")
        assert proxy is not None
        assert proxy.name == "yfinance"
        assert "ohlcv" in proxy.tags

    def test_get_missing_tool(self, registry: ToolRegistry) -> None:
        """get() should raise KeyError for unknown tools."""
        with pytest.raises(KeyError, match="not found"):
            registry.get("nonexistent")

    def test_find_by_tag_macro(self, registry: ToolRegistry) -> None:
        """find_by_tag('macro') should return only fred."""
        results = registry.find_by_tag("macro")
        names = [p.name for p in results]
        assert names == ["fred"]

    def test_find_by_tag_ohlcv(self, registry: ToolRegistry) -> None:
        """find_by_tag('ohlcv') should return yfinance and alpha_vantage."""
        results = registry.find_by_tag("ohlcv")
        names = [p.name for p in results]
        assert "yfinance" in names
        assert "alpha_vantage" in names

    def test_find_by_tag_unknown(self, registry: ToolRegistry) -> None:
        """find_by_tag with unknown tag should return empty list."""
        results = registry.find_by_tag("nonexistent_tag")
        assert results == []

    @pytest.mark.asyncio
    async def test_fallback_triggered(self, registry: ToolRegistry) -> None:
        """When yfinance fails, should fallback to alpha_vantage."""
        # Mock yfinance to fail
        yf_proxy = registry.get("yfinance")
        yf_proxy._rl = None
        yf_proxy._cache = None
        yf_proxy._adapter.fetch = AsyncMock(
            return_value=ToolResult(success=False, error="503", source="yfinance")
        )

        # Mock alpha_vantage to succeed
        av_proxy = registry.get("alpha_vantage")
        av_proxy._rl = None
        av_proxy._cache = None
        av_proxy._adapter.fetch = AsyncMock(
            return_value=ToolResult(
                success=True,
                data={"price": 450.0},
                source="alpha_vantage",
            )
        )

        result = await yf_proxy.fetch(ticker="QQQ")

        assert result.success is True
        assert result.source == "alpha_vantage"
        av_proxy._adapter.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_after_failures(self, registry: ToolRegistry) -> None:
        """After failure_threshold failures, circuit breaker should block."""
        proxy = registry.get("fred")
        # Disable rate limiter and cache for this test
        proxy._rl = None
        proxy._cache = None

        # Fail 3 times
        proxy._adapter.fetch = AsyncMock(
            return_value=ToolResult(success=False, error="fail", source="fred")
        )
        for _ in range(3):
            await proxy.fetch(series_id="FEDFUNDS")

        # 4th call should be blocked by CB
        result = await proxy.fetch(series_id="FEDFUNDS")
        assert result.success is False
        assert "Circuit breaker open" in result.error
