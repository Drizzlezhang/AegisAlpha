"""Test DataHarvesterAgent — full mode, lightweight mode, error handling, edge cases."""
from typing import Any
from unittest.mock import AsyncMock

import pytest

from aegis.agents.data_harvester_agent import DataHarvesterAgent
from aegis.pipeline.state import PipelineState
from aegis.tools.base import ToolResult


class MockYFinanceTool:
    """Mock yfinance tool returning OHLCV data."""

    name = "yfinance"

    async def fetch(self, **kwargs: Any) -> ToolResult:
        ticker = kwargs.get("ticker", "UNKNOWN")
        return ToolResult(
            success=True,
            data={"ticker": ticker, "ohlcv": {"open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000000}},
            source="yfinance",
        )


class MockFailingYFinanceTool:
    """Mock yfinance tool that always fails."""

    name = "yfinance"

    async def fetch(self, **kwargs: Any) -> ToolResult:
        return ToolResult(success=False, error="API rate limit exceeded", source="yfinance")


class MockFredTool:
    """Mock FRED tool returning macro data."""

    name = "fred"

    async def fetch(self, **kwargs: Any) -> ToolResult:
        series = kwargs.get("series", "")
        data = {}
        for s in series.split(","):
            data[s.strip()] = {"value": 4.5, "unit": "percent"}
        return ToolResult(success=True, data=data, source="fred")


class MockTavilyTool:
    """Mock Tavily tool returning news."""

    name = "tavily"

    async def fetch(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            success=True,
            data=[{"title": "News 1", "url": "http://example.com/1"}],
            source="tavily",
        )


@pytest.fixture
def mock_tools_all() -> dict[str, Any]:
    return {
        "yfinance": MockYFinanceTool(),
        "fred": MockFredTool(),
        "tavily": MockTavilyTool(),
    }


@pytest.fixture
def mock_tools_failing_yfinance() -> dict[str, Any]:
    return {
        "yfinance": MockFailingYFinanceTool(),
        "fred": MockFredTool(),
        "tavily": MockTavilyTool(),
    }


@pytest.fixture
def mock_tools_minimal() -> dict[str, Any]:
    return {
        "yfinance": MockYFinanceTool(),
        "fred": MockFredTool(),
    }


class TestDataHarvesterAgent:
    """Verify DataHarvesterAgent behavior."""

    # --- Manifest ---

    def test_manifest_fields(self) -> None:
        """AC-6: manifest should have correct field values."""
        m = DataHarvesterAgent.manifest
        assert m.name == "data_harvester"
        assert m.version == "0.1.0"
        assert m.requires == []
        assert "market_data" in m.provides
        assert "macro_data" in m.provides
        assert "data" in m.tags
        assert "harvester" in m.tags
        assert m.llm_dependency is False
        assert m.parallel_group is None
        assert m.pipeline_mode == "both"

    # --- Full mode ---

    @pytest.mark.asyncio
    async def test_full_mode_fetches_all_sources(
        self, mock_memory: Any, mock_tools_all: dict[str, Any], mock_config: Any
    ) -> None:
        """AC-1: full mode should fetch OHLCV + FRED + Tavily."""
        agent = DataHarvesterAgent(memory=mock_memory, tools=mock_tools_all, config=mock_config)
        state = PipelineState(tickers=["QQQ"], pipeline_mode="full")

        result = await agent.run(state)

        assert "QQQ" in result.market_data
        assert "ohlcv" in result.market_data["QQQ"]
        assert "news" in result.market_data["QQQ"]
        assert "FEDFUNDS" in result.macro_data or "raw" in result.macro_data
        assert "VIX" in result.macro_data or "raw" in result.macro_data

    # --- Lightweight mode ---

    @pytest.mark.asyncio
    async def test_lightweight_mode_skips_news(
        self, mock_memory: Any, mock_tools_all: dict[str, Any], mock_config: Any
    ) -> None:
        """AC-2: lightweight mode should skip Tavily news."""
        agent = DataHarvesterAgent(memory=mock_memory, tools=mock_tools_all, config=mock_config)
        state = PipelineState(tickers=["QQQ"], pipeline_mode="lightweight")

        result = await agent.run(state)

        assert "QQQ" in result.market_data
        assert "news" not in result.market_data["QQQ"]

    @pytest.mark.asyncio
    async def test_lightweight_mode_only_vix_in_macro(
        self, mock_memory: Any, mock_tools_all: dict[str, Any], mock_config: Any
    ) -> None:
        """AC-2: lightweight mode should only fetch VIX from FRED."""
        agent = DataHarvesterAgent(memory=mock_memory, tools=mock_tools_all, config=mock_config)
        state = PipelineState(tickers=["QQQ"], pipeline_mode="lightweight")

        result = await agent.run(state)

        # In lightweight mode, only VIX should be requested
        assert "FEDFUNDS" not in result.macro_data

    # --- Error handling ---

    @pytest.mark.asyncio
    async def test_tool_failure_writes_error_flag(
        self, mock_memory: Any, mock_tools_failing_yfinance: dict[str, Any], mock_config: Any
    ) -> None:
        """AC-3: Tool failure should write error_flags, not raise exception."""
        agent = DataHarvesterAgent(
            memory=mock_memory, tools=mock_tools_failing_yfinance, config=mock_config
        )
        state = PipelineState(tickers=["QQQ"], pipeline_mode="full")

        result = await agent.run(state)

        assert len(result.error_flags) > 0
        assert any("yfinance" in str(flag.get("error", "")) for flag in result.error_flags)

    @pytest.mark.asyncio
    async def test_missing_tool_writes_error_flag(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Missing tool in registry should write error_flag."""
        agent = DataHarvesterAgent(memory=mock_memory, tools={}, config=mock_config)
        state = PipelineState(tickers=["QQQ"], pipeline_mode="full")

        result = await agent.run(state)

        assert len(result.error_flags) > 0
        assert any("not found" in str(flag.get("error", "")) for flag in result.error_flags)

    # --- Edge cases ---

    @pytest.mark.asyncio
    async def test_empty_tickers_skips_all(
        self, mock_memory: Any, mock_tools_all: dict[str, Any], mock_config: Any
    ) -> None:
        """Edge-1: empty tickers should skip all tool calls."""
        agent = DataHarvesterAgent(memory=mock_memory, tools=mock_tools_all, config=mock_config)
        state = PipelineState(tickers=[], pipeline_mode="full")

        result = await agent.run(state)

        assert result.market_data == {}
        assert result.macro_data == {}

    @pytest.mark.asyncio
    async def test_multiple_tickers_full_mode(
        self, mock_memory: Any, mock_tools_all: dict[str, Any], mock_config: Any
    ) -> None:
        """Full mode should fetch data for all tickers."""
        agent = DataHarvesterAgent(memory=mock_memory, tools=mock_tools_all, config=mock_config)
        state = PipelineState(tickers=["QQQ", "SPY"], pipeline_mode="full")

        result = await agent.run(state)

        assert "QQQ" in result.market_data
        assert "SPY" in result.market_data
        assert "news" in result.market_data["QQQ"]
        assert "news" in result.market_data["SPY"]
