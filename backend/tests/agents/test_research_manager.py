"""Test ResearchManagerAgent — ranking, pending_triggers, LLM failure, manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from aegis.agents.research_manager_agent import ResearchManagerAgent
from aegis.pipeline.state import PipelineState

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _llm_response(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "content": json.dumps({"recommendations": recommendations}),
        "usage": {"total_tokens": 100},
        "model": "gpt-4o",
    }


class TestResearchManager:
    @pytest.mark.asyncio
    async def test_generates_and_sorts_recommendations(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should generate recommendations sorted by urgency × score."""
        mock_response = _llm_response(
            [
                {
                    "ticker": "QQQ",
                    "action": "buy",
                    "strategy": "leaps_call",
                    "rationale": "bullish setup",
                    "urgency": "low",
                    "score": 90,
                    "delta_dollars_delta": 500,
                },
                {
                    "ticker": "QQQ",
                    "action": "buy",
                    "strategy": "stock",
                    "rationale": "momentum",
                    "urgency": "high",
                    "score": 70,
                    "delta_dollars_delta": 300,
                },
                {
                    "ticker": "QQQ",
                    "action": "hold",
                    "strategy": "stock",
                    "rationale": "wait",
                    "urgency": "medium",
                    "score": 50,
                    "delta_dollars_delta": 0,
                },
            ]
        )
        with patch("aegis.agents.research_manager_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step2={"QQQ": {"contracts": []}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.8}},
                positions={"total_nav": 100000.0, "cash": 50000.0, "holdings": []},
            )
            result = await agent.run(state)
            recs = result.recommendations
            assert len(recs) == 3
            # high×70=210 > medium×50=100 > low×90=90
            assert recs[0].urgency == "high"
            assert recs[1].urgency == "medium"
            assert recs[2].urgency == "low"

    @pytest.mark.asyncio
    async def test_sets_pending_triggers_placeholder(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should set pending_triggers = [] as M1 placeholder."""
        mock_response = _llm_response(
            [
                {
                    "ticker": "QQQ",
                    "action": "hold",
                    "strategy": "stock",
                    "rationale": "wait",
                    "urgency": "medium",
                    "score": 50,
                    "delta_dollars_delta": 0,
                },
            ]
        )
        with patch("aegis.agents.research_manager_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step2={},
                debate_results={},
                positions={"total_nav": 100000.0, "cash": 50000.0, "holdings": []},
            )
            result = await agent.run(state)
            assert result.pending_triggers == []

    @pytest.mark.asyncio
    async def test_handles_llm_json_parse_failure(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should write error_flags on JSON parse failure, not crash."""
        with patch("aegis.agents.research_manager_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(
                return_value={"content": "not json", "usage": {}, "model": "gpt-4o"}
            )
            mock_llm_cls.return_value = mock_llm

            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step2={},
                debate_results={},
                positions={"total_nav": 100000.0, "cash": 50000.0, "holdings": []},
            )
            result = await agent.run(state)
            assert len(result.error_flags) > 0
            assert result.error_flags[0]["agent"] == "research_manager"

    @pytest.mark.asyncio
    async def test_handles_llm_exception(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should write error_flags on LLM exception, not crash."""
        with patch("aegis.agents.research_manager_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(side_effect=RuntimeError("API timeout"))
            mock_llm_cls.return_value = mock_llm

            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step2={},
                debate_results={},
                positions={"total_nav": 100000.0, "cash": 50000.0, "holdings": []},
            )
            result = await agent.run(state)
            assert len(result.error_flags) > 0
            assert result.error_flags[0]["agent"] == "research_manager"

    @pytest.mark.asyncio
    async def test_writes_extensions(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should write synthesis_raw metadata to extensions."""
        mock_response = _llm_response(
            [
                {
                    "ticker": "QQQ",
                    "action": "buy",
                    "strategy": "leaps_call",
                    "rationale": "test",
                    "urgency": "high",
                    "score": 80,
                    "delta_dollars_delta": 500,
                },
            ]
        )
        with patch("aegis.agents.research_manager_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step2={"QQQ": {"contracts": []}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.8}},
                positions={"total_nav": 100000.0, "cash": 50000.0, "holdings": []},
            )
            result = await agent.run(state)
            assert "research_manager" in result.extensions
            ext = result.extensions["research_manager"]
            assert "synthesis_raw" in ext
            assert ext["synthesis_raw"]["total_recommendations"] == 1

    def test_manifest_compliance(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        m = agent.manifest
        assert m.name == "research_manager"
        assert m.llm_dependency is True
        assert m.pipeline_mode == "full"
        assert "research" in m.tags
        assert "ranking" in m.tags
