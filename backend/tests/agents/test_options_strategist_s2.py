"""Test OptionsStrategistS2Agent — contract generation, stop_loss modes, empty candidates, manifest."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from aegis.agents.options_strategist_s2_agent import OptionsStrategistS2Agent
from aegis.pipeline.state import PipelineState

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _llm_response(contracts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "content": json.dumps({"contracts": contracts}),
        "usage": {"total_tokens": 100},
        "model": "gpt-4o",
    }


def _make_agent(mock_memory: Any, mock_tools: Any, mock_config: Any) -> OptionsStrategistS2Agent:
    """Construct agent with mocked LLMClient."""
    with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=_llm_response([]))
        mock_llm_cls.return_value = mock_llm
        return OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)


class TestOptionsStrategistS2:
    @pytest.mark.asyncio
    async def test_generates_contracts_with_support_based_stop(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should generate contracts with support_based stop_loss when levels available."""
        mock_response = _llm_response([
            {"strike": 450.0, "type": "call", "entry_price": 22.50, "rationale": "strong support", "entry_mode": "passive"},
        ])
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [{"strike": 450.0, "type": "call", "dte": 400, "delta": 0.6, "iv": 0.25, "bid": 22.0, "ask": 23.0}]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.85, "rationale": "strong momentum"}},
                analyst_outputs={"levels": {"QQQ": {"support_levels": [400.0], "resistance_levels": [480.0]}}},
            )
            result = await agent.run(state)
            output = result.options_step2["QQQ"]
            assert "contracts" in output
            assert len(output["contracts"]) == 1
            c = output["contracts"][0]
            assert "stop_loss" in c
            assert c["stop_loss"]["mode"] == "support_based"

    @pytest.mark.asyncio
    async def test_falls_back_to_fixed_pct_when_no_levels(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should use fixed_pct stop_loss when no support levels available."""
        mock_response = _llm_response([
            {"strike": 450.0, "type": "call", "entry_price": 22.50, "rationale": "momentum play", "entry_mode": "passive"},
        ])
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [{"strike": 450.0, "type": "call", "dte": 400, "delta": 0.6, "iv": 0.25, "bid": 22.0, "ask": 23.0}]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.85, "rationale": "momentum"}},
                analyst_outputs={"levels": {"QQQ": {"support_levels": [], "resistance_levels": []}}},
            )
            result = await agent.run(state)
            c = result.options_step2["QQQ"]["contracts"][0]
            assert c["stop_loss"]["mode"] == "fixed_pct"

    @pytest.mark.asyncio
    async def test_skips_llm_when_no_candidates(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should return empty dict without calling LLM when no candidates."""
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock()
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": []}},
                debate_results={},
                analyst_outputs={},
            )
            result = await agent.run(state)
            assert result.options_step2["QQQ"] == {}
            # LLM should not have been called
            mock_llm.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_llm_json_parse_failure(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should write error_flags on JSON parse failure, not crash."""
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value={"content": "not valid json", "usage": {}, "model": "gpt-4o"})
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [{"strike": 450.0, "type": "call", "dte": 400, "delta": 0.6, "iv": 0.25, "bid": 22.0, "ask": 23.0}]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.85, "rationale": "test"}},
                analyst_outputs={},
            )
            result = await agent.run(state)
            assert len(result.error_flags) > 0
            assert result.error_flags[0]["agent"] == "options_strategist_s2"

    @pytest.mark.asyncio
    async def test_handles_llm_exception(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should write error_flags on LLM exception, not crash."""
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(side_effect=RuntimeError("API timeout"))
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [{"strike": 450.0, "type": "call", "dte": 400, "delta": 0.6, "iv": 0.25, "bid": 22.0, "ask": 23.0}]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.85, "rationale": "test"}},
                analyst_outputs={},
            )
            result = await agent.run(state)
            assert len(result.error_flags) > 0
            assert result.error_flags[0]["agent"] == "options_strategist_s2"

    @pytest.mark.asyncio
    async def test_writes_extensions(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should write s2_raw metadata to extensions."""
        mock_response = _llm_response([
            {"strike": 450.0, "type": "call", "entry_price": 22.50, "rationale": "test", "entry_mode": "passive"},
        ])
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [{"strike": 450.0, "type": "call", "dte": 400, "delta": 0.6, "iv": 0.25, "bid": 22.0, "ask": 23.0}]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.85, "rationale": "test"}},
                analyst_outputs={"levels": {"QQQ": {"support_levels": [400.0], "resistance_levels": []}}},
            )
            result = await agent.run(state)
            assert "options_strategist_s2" in result.extensions
            ext = result.extensions["options_strategist_s2"]
            assert "s2_raw" in ext
            assert ext["s2_raw"]["contracts_count"] == 1

    def test_manifest_compliance(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient"):
            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
        m = agent.manifest
        assert m.name == "options_strategist_s2"
        assert m.llm_dependency is True
        assert m.pipeline_mode == "full"
        assert "options" in m.tags
        assert "strategy" in m.tags
