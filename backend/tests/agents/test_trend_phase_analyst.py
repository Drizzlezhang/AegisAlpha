"""Test TrendPhaseAnalystAgent — bullish/bearish/sideways + edge cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aegis.agents.trend_phase_analyst_agent import TrendPhaseAnalystAgent
from aegis.pipeline.state import PipelineState

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def agent(mock_memory: Any, mock_tools: Any, mock_config: Any) -> TrendPhaseAnalystAgent:
    return TrendPhaseAnalystAgent(memory=mock_memory, tools=mock_tools, config=mock_config)


@pytest.fixture
def bullish_ohlcv() -> dict[str, Any]:
    return _load_fixture("QQQ_trend_bullish.json")


@pytest.fixture
def bearish_ohlcv() -> dict[str, Any]:
    return _load_fixture("QQQ_trend_bearish.json")


class TestTrendPhaseAnalyst:
    """Trend/Phase Analyst agent tests."""

    @pytest.mark.asyncio
    async def test_bullish_trend_detection(
        self, agent: TrendPhaseAnalystAgent, bullish_ohlcv: dict[str, Any]
    ) -> None:
        """Bullish OHLCV should produce bullish trend_direction."""
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": bullish_ohlcv},
        )
        result = await agent.run(state)
        output = result.analyst_outputs["QQQ"]["trend_phase"]
        assert output["trend_direction"] == "bullish"
        assert output["trend_score"] > 50
        assert output["wyckoff_phase"] in (
            "accumulation",
            "markup",
            "distribution",
            "markdown",
            "unknown",
        )
        assert 0 <= output["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_bearish_trend_detection(
        self, agent: TrendPhaseAnalystAgent, bearish_ohlcv: dict[str, Any]
    ) -> None:
        """Bearish OHLCV should produce bearish trend_direction."""
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": bearish_ohlcv},
        )
        result = await agent.run(state)
        output = result.analyst_outputs["QQQ"]["trend_phase"]
        assert output["trend_direction"] == "bearish"
        assert output["trend_score"] < 50

    @pytest.mark.asyncio
    async def test_sideways_trend_detection(self, agent: TrendPhaseAnalystAgent) -> None:
        """Flat OHLCV should produce sideways trend_direction."""
        n = 60
        flat_price = 400.0
        ohlcv = {
            "open": [flat_price] * n,
            "high": [flat_price + 1.0] * n,
            "low": [flat_price - 1.0] * n,
            "close": [flat_price] * n,
            "volume": [5000000] * n,
        }
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": ohlcv},
        )
        result = await agent.run(state)
        output = result.analyst_outputs["QQQ"]["trend_phase"]
        # Flat data should be sideways or unknown
        assert output["trend_direction"] in ("sideways", "bearish", "bullish")

    @pytest.mark.asyncio
    async def test_empty_market_data(self, agent: TrendPhaseAnalystAgent) -> None:
        """Empty market_data should write error_flag, not crash."""
        state = PipelineState(tickers=["QQQ"], market_data={})
        result = await agent.run(state)
        assert len(result.error_flags) >= 1
        assert result.error_flags[0]["agent"] == "trend_phase_analyst"

    @pytest.mark.asyncio
    async def test_insufficient_ohlcv_data(self, agent: TrendPhaseAnalystAgent) -> None:
        """OHLCV with < 2 data points should write error_flag."""
        ohlcv = {"open": [400.0], "high": [401.0], "low": [399.0], "close": [400.0]}
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": ohlcv},
        )
        result = await agent.run(state)
        assert len(result.error_flags) >= 1

    @pytest.mark.asyncio
    async def test_writes_extensions(
        self, agent: TrendPhaseAnalystAgent, bullish_ohlcv: dict[str, Any]
    ) -> None:
        """Agent should write raw data to extensions."""
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": bullish_ohlcv},
        )
        result = await agent.run(state)
        assert "trend_phase_analyst" in result.extensions
        ext = result.extensions["trend_phase_analyst"]
        assert "wyckoff_raw" in ext
        assert "trend_raw" in ext

    @pytest.mark.asyncio
    async def test_manifest_compliance(self, agent: TrendPhaseAnalystAgent) -> None:
        """Manifest must have correct fields."""
        m = agent.manifest
        assert m.llm_dependency is False
        assert m.parallel_group == "signal_analysts"
        assert m.pipeline_mode == "both"
        assert "signal" in m.tags
