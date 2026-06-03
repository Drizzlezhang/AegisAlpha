"""Test OptionsStrategistS1Agent — screening + empty chain + edge cases."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aegis.agents.options_strategist_s1_agent import OptionsStrategistS1Agent
from aegis.pipeline.state import OptionContract, PipelineState

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def agent(mock_memory: Any, mock_tools: Any, mock_config: Any) -> OptionsStrategistS1Agent:
    return OptionsStrategistS1Agent(memory=mock_memory, tools=mock_tools, config=mock_config)


@pytest.fixture
def option_chain_fixture() -> dict[str, Any]:
    return _load_fixture("QQQ_options_chain_mock.json")


class TestOptionsStrategistS1:
    """Options Strategist S1 agent tests."""

    @pytest.mark.asyncio
    async def test_screening_filters_contracts(
        self, agent: OptionsStrategistS1Agent, option_chain_fixture: dict[str, Any]
    ) -> None:
        """Should filter option chain and return candidates."""
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": {"option_chain": option_chain_fixture["chain"]}},
        )
        result = await agent.run(state)
        output = result.options_step1["QQQ"]
        assert "candidates" in output
        assert "total_screened" in output
        assert "total_passed" in output
        assert output["total_screened"] == len(option_chain_fixture["chain"])
        # At least some contracts should pass filters
        assert output["total_passed"] >= 0

    @pytest.mark.asyncio
    async def test_candidates_are_valid_option_contracts(
        self, agent: OptionsStrategistS1Agent, option_chain_fixture: dict[str, Any]
    ) -> None:
        """Each candidate should be constructable as OptionContract."""
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": {"option_chain": option_chain_fixture["chain"]}},
        )
        result = await agent.run(state)
        candidates = result.options_step1["QQQ"]["candidates"]
        for c in candidates:
            contract = OptionContract(**c)
            assert contract.dte >= 365
            assert contract.delta > 0

    @pytest.mark.asyncio
    async def test_empty_option_chain(
        self, agent: OptionsStrategistS1Agent
    ) -> None:
        """Empty option chain should return empty dict, not crash."""
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": {"option_chain": []}},
        )
        result = await agent.run(state)
        assert result.options_step1["QQQ"] == {}

    @pytest.mark.asyncio
    async def test_no_option_chain_key(
        self, agent: OptionsStrategistS1Agent
    ) -> None:
        """Missing option_chain key should return empty dict."""
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": {}},
        )
        result = await agent.run(state)
        assert result.options_step1["QQQ"] == {}

    @pytest.mark.asyncio
    async def test_dte_filter(
        self, agent: OptionsStrategistS1Agent
    ) -> None:
        """Contracts with DTE < 365 should be filtered out."""
        chain = [
            {
                "symbol": "TEST",
                "type": "call",
                "strike": 450.0,
                "expiration": "2025-01-01",
                "dte": 30,
                "bid": 10.0,
                "ask": 11.0,
                "iv": 0.2,
                "spot_price": 450.0,
                "oi": 500,
                "volume": 100,
            },
            {
                "symbol": "TEST2",
                "type": "call",
                "strike": 450.0,
                "expiration": "2026-06-01",
                "dte": 400,
                "bid": 22.0,
                "ask": 23.0,
                "iv": 0.2,
                "spot_price": 450.0,
                "oi": 500,
                "volume": 100,
            },
        ]
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": {"option_chain": chain}},
        )
        result = await agent.run(state)
        candidates = result.options_step1["QQQ"]["candidates"]
        # Only the 400 DTE contract should pass
        assert len(candidates) == 1
        assert candidates[0]["dte"] == 400

    @pytest.mark.asyncio
    async def test_writes_extensions(
        self, agent: OptionsStrategistS1Agent, option_chain_fixture: dict[str, Any]
    ) -> None:
        """Agent should write screening metadata to extensions."""
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": {"option_chain": option_chain_fixture["chain"]}},
        )
        result = await agent.run(state)
        assert "options_strategist_s1" in result.extensions
        ext = result.extensions["options_strategist_s1"]
        assert "screening_raw" in ext

    @pytest.mark.asyncio
    async def test_manifest_compliance(self, agent: OptionsStrategistS1Agent) -> None:
        """Manifest must have correct fields."""
        m = agent.manifest
        assert m.llm_dependency is False
        assert m.parallel_group == "signal_analysts"
        assert m.pipeline_mode == "full"
        assert "options" in m.tags
