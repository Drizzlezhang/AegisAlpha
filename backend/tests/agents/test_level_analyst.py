"""Test LevelAnalystAgent — support/resistance + GEX + edge cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aegis.agents.level_analyst_agent import LevelAnalystAgent
from aegis.pipeline.state import PipelineState

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def agent(mock_memory: Any, mock_tools: Any, mock_config: Any) -> LevelAnalystAgent:
    return LevelAnalystAgent(memory=mock_memory, tools=mock_tools, config=mock_config)


@pytest.fixture
def bullish_ohlcv() -> dict[str, Any]:
    return _load_fixture("QQQ_trend_bullish.json")


@pytest.fixture
def gex_data() -> dict[str, Any]:
    return _load_fixture("QQQ_gex_data.json")


class TestLevelAnalyst:
    """Level Analyst agent tests."""

    @pytest.mark.asyncio
    async def test_support_resistance_detection(
        self, agent: LevelAnalystAgent, bullish_ohlcv: dict[str, Any]
    ) -> None:
        """Should identify support and resistance levels."""
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": bullish_ohlcv},
        )
        result = await agent.run(state)
        output = result.analyst_outputs["QQQ"]["levels"]
        assert "support_levels" in output
        assert "resistance_levels" in output
        assert isinstance(output["support_levels"], list)
        assert isinstance(output["resistance_levels"], list)
        # All support levels should be floats
        for s in output["support_levels"]:
            assert isinstance(s, float)

    @pytest.mark.asyncio
    async def test_support_levels_consumable_by_stop_loss(
        self, agent: LevelAnalystAgent, bullish_ohlcv: dict[str, Any]
    ) -> None:
        """support_levels must be list[float] for stop_loss consumption."""
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": bullish_ohlcv},
        )
        result = await agent.run(state)
        support_levels = result.analyst_outputs["QQQ"]["levels"]["support_levels"]
        # In a smooth uptrend there may be no swing lows, but the field must be list[float]
        assert isinstance(support_levels, list)
        assert all(isinstance(lvl, float) for lvl in support_levels)

    @pytest.mark.asyncio
    async def test_gex_integration(
        self, agent: LevelAnalystAgent, bullish_ohlcv: dict[str, Any], gex_data: dict[str, Any]
    ) -> None:
        """With GEX data, should include gamma_flip_level and gex_signal."""
        market_data = {**bullish_ohlcv, "gex": gex_data}
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": market_data},
        )
        result = await agent.run(state)
        output = result.analyst_outputs["QQQ"]["levels"]
        assert "gamma_flip_level" in output
        assert "gex_signal" in output
        assert output["gex_signal"] in ("positive", "negative", "neutral")

    @pytest.mark.asyncio
    async def test_no_gex_fallback(
        self, agent: LevelAnalystAgent, bullish_ohlcv: dict[str, Any]
    ) -> None:
        """Without GEX data, should still work with neutral defaults."""
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": bullish_ohlcv},
        )
        result = await agent.run(state)
        output = result.analyst_outputs["QQQ"]["levels"]
        assert output["gamma_flip_level"] is None
        assert output["gex_signal"] == "neutral"

    @pytest.mark.asyncio
    async def test_empty_market_data(self, agent: LevelAnalystAgent) -> None:
        """Empty market_data should write error_flag, not crash."""
        state = PipelineState(tickers=["QQQ"], market_data={})
        result = await agent.run(state)
        assert len(result.error_flags) >= 1
        assert result.error_flags[0]["agent"] == "level_analyst"

    @pytest.mark.asyncio
    async def test_writes_extensions(
        self, agent: LevelAnalystAgent, bullish_ohlcv: dict[str, Any]
    ) -> None:
        """Agent should write raw data to extensions."""
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": bullish_ohlcv},
        )
        result = await agent.run(state)
        assert "level_analyst" in result.extensions
        ext = result.extensions["level_analyst"]
        assert "sr_raw" in ext
        assert "volume_profile_raw" in ext

    @pytest.mark.asyncio
    async def test_manifest_compliance(self, agent: LevelAnalystAgent) -> None:
        """Manifest must have correct fields."""
        m = agent.manifest
        assert m.llm_dependency is False
        assert m.parallel_group == "signal_analysts"
        assert m.pipeline_mode == "both"
        assert "signal" in m.tags
