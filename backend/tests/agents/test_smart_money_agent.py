"""Test SmartMoneyAgent — score computation, narrative, manifest, error handling."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.agents.smart_money_agent import SmartMoneyAgent
from aegis.pipeline.state import PipelineState
from aegis.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(tickers: list[str] | None = None) -> PipelineState:
    return PipelineState(tickers=tickers or ["QQQ"])


def _mock_tool_result(success: bool, data: Any) -> MagicMock:
    mock = MagicMock()
    mock.fetch = AsyncMock(return_value=ToolResult(success=success, data=data, source="mock"))
    return mock


def _mock_llm_response(content: str = "Smart money is leaning bullish.") -> dict[str, Any]:
    return {
        "content": content,
        "usage": {"total_tokens": 50},
        "model": "gpt-4o-mini",
    }


# ---------------------------------------------------------------------------
# Score computation tests
# ---------------------------------------------------------------------------


class TestSmartMoneyScore:
    """Test _compute_score static method."""

    def test_score_bullish_high_confidence(self) -> None:
        """All calls, high premium → high bullish score."""
        unusual = [
            {"type": "call", "strike": 500, "expiration": "2026-07-17", "premium": 300000, "size": 500},
            {"type": "call", "strike": 510, "expiration": "2026-07-17", "premium": 200000, "size": 400},
            {"type": "call", "strike": 520, "expiration": "2026-07-17", "premium": 100000, "size": 300},
        ]
        oi = {"call_oi_delta": 2000, "put_oi_delta": -500, "oi_delta": 5.0, "daily_oi": []}

        score, direction = SmartMoneyAgent._compute_score(unusual, oi)

        # call_ratio = 1.0, direction_score = abs(1.0-0.5)*80 = 40
        # premium_bias = 1.0, premium_score = abs(1.0-0.5)*60 = 30
        # oi_score = min(5.0*3, 30) = 15
        # total = 0.35*40 + 0.35*30 + 0.30*15 = 14 + 10.5 + 4.5 = 29.0
        assert score == pytest.approx(29.0, rel=1e-2)
        assert direction == "bullish"

    def test_score_bearish(self) -> None:
        """All puts → bearish score."""
        unusual = [
            {"type": "put", "strike": 460, "expiration": "2026-07-17", "premium": 250000, "size": 500},
            {"type": "put", "strike": 450, "expiration": "2026-07-17", "premium": 150000, "size": 300},
        ]
        oi = {"call_oi_delta": -1000, "put_oi_delta": 3000, "oi_delta": -4.0, "daily_oi": []}

        score, direction = SmartMoneyAgent._compute_score(unusual, oi)

        # call_ratio = 0.0, direction_score = abs(0.0-0.5)*80 = 40
        # premium_bias = 0.0, premium_score = abs(0.0-0.5)*60 = 30
        # oi_score = min(4.0*3, 30) = 12
        # total = 0.35*40 + 0.35*30 + 0.30*12 = 14 + 10.5 + 3.6 = 28.1
        assert score == pytest.approx(28.1, rel=1e-2)
        assert direction == "bearish"

    def test_score_neutral(self) -> None:
        """Balanced calls/puts → neutral."""
        unusual = [
            {"type": "call", "strike": 500, "expiration": "2026-07-17", "premium": 100000, "size": 200},
            {"type": "put", "strike": 480, "expiration": "2026-07-17", "premium": 100000, "size": 200},
        ]
        oi = {"call_oi_delta": 0, "put_oi_delta": 0, "oi_delta": 0, "daily_oi": []}

        score, direction = SmartMoneyAgent._compute_score(unusual, oi)

        # call_ratio = 0.5, direction_score = 0
        # premium_bias = 0.5, premium_score = 0
        # oi_score = 0
        # total = 0
        assert score == 0.0
        assert direction == "neutral"

    def test_score_empty_options(self) -> None:
        """No unusual options → neutral with score 0."""
        score, direction = SmartMoneyAgent._compute_score(
            [], {"call_oi_delta": 0, "put_oi_delta": 0, "oi_delta": 0, "daily_oi": []}
        )
        assert score == 0.0
        assert direction == "neutral"

    def test_score_oi_capped_at_30(self) -> None:
        """OI score should be capped at 30."""
        unusual = [
            {"type": "call", "strike": 500, "expiration": "2026-07-17", "premium": 100000, "size": 200},
        ]
        oi = {"call_oi_delta": 5000, "put_oi_delta": -5000, "oi_delta": 20.0, "daily_oi": []}

        score, direction = SmartMoneyAgent._compute_score(unusual, oi)

        # call_ratio = 1.0, direction_score = 40
        # premium_bias = 1.0, premium_score = 30
        # oi_score = min(20*3, 30) = 30 (capped)
        # total = 0.35*40 + 0.35*30 + 0.30*30 = 14 + 10.5 + 9 = 33.5
        assert score == pytest.approx(33.5, rel=1e-2)
        assert direction == "bullish"


# ---------------------------------------------------------------------------
# Agent run tests
# ---------------------------------------------------------------------------


class TestSmartMoneyAgentRun:
    @pytest.mark.asyncio
    async def test_run_success_with_data(
        self, mock_memory: Any, mock_config: Any
    ) -> None:
        """Agent should populate smart_money_data for each ticker."""
        uw_tool = _mock_tool_result(
            True,
            [
                {"type": "call", "strike": 500, "expiration": "2026-07-17", "premium": 200000, "size": 400},
                {"type": "put", "strike": 460, "expiration": "2026-07-17", "premium": 100000, "size": 200},
            ],
        )
        oi_tool = _mock_tool_result(
            True,
            {"call_oi_delta": 1000, "put_oi_delta": -500, "oi_delta": 2.0, "daily_oi": []},
        )
        tools = {"unusual_whales": uw_tool, "oi_change": oi_tool}

        with patch("aegis.agents.smart_money_agent.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(return_value=_mock_llm_response("Bullish flow detected."))
            mock_llm_cls.return_value = mock_llm

            agent = SmartMoneyAgent(memory=mock_memory, tools=tools, config=mock_config)
            state = _make_state()
            result = await agent.run(state)

        assert "QQQ" in result.smart_money_data
        data = result.smart_money_data["QQQ"]
        assert "smart_money_score" in data
        assert data["direction_bias"] in ("bullish", "bearish", "neutral")
        assert len(data["unusual_options"]) <= 5
        assert data["narrative"] == "Bullish flow detected."
        assert "smart_money_agent" in result.agent_timings

    @pytest.mark.asyncio
    async def test_run_fallback_to_market_chameleon(
        self, mock_memory: Any, mock_config: Any
    ) -> None:
        """When UW fails, should fallback to MarketChameleon."""
        uw_tool = _mock_tool_result(False, None)
        mc_tool = _mock_tool_result(
            True,
            [
                {"type": "call", "strike": 500, "expiration": "2026-07-17", "premium": 150000, "size": 300},
            ],
        )
        oi_tool = _mock_tool_result(
            True,
            {"call_oi_delta": 500, "put_oi_delta": -200, "oi_delta": 1.0, "daily_oi": []},
        )
        tools = {"unusual_whales": uw_tool, "market_chameleon": mc_tool, "oi_change": oi_tool}

        with patch("aegis.agents.smart_money_agent.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(return_value=_mock_llm_response("Moderate bullish."))
            mock_llm_cls.return_value = mock_llm

            agent = SmartMoneyAgent(memory=mock_memory, tools=tools, config=mock_config)
            state = _make_state()
            result = await agent.run(state)

        assert "QQQ" in result.smart_money_data
        assert len(result.smart_money_data["QQQ"]["unusual_options"]) == 1

    @pytest.mark.asyncio
    async def test_run_all_sources_unavailable(
        self, mock_memory: Any, mock_config: Any
    ) -> None:
        """When all data sources fail, should still complete with empty data."""
        uw_tool = _mock_tool_result(False, None)
        mc_tool = _mock_tool_result(False, None)
        oi_tool = _mock_tool_result(False, None)
        tools = {"unusual_whales": uw_tool, "market_chameleon": mc_tool, "oi_change": oi_tool}

        with patch("aegis.agents.smart_money_agent.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(return_value=_mock_llm_response(""))
            mock_llm_cls.return_value = mock_llm

            agent = SmartMoneyAgent(memory=mock_memory, tools=tools, config=mock_config)
            state = _make_state()
            result = await agent.run(state)

        assert "QQQ" in result.smart_money_data
        data = result.smart_money_data["QQQ"]
        assert data["smart_money_score"] == 0.0
        assert data["direction_bias"] == "neutral"
        assert data["unusual_options"] == []

    @pytest.mark.asyncio
    async def test_run_empty_tickers(
        self, mock_memory: Any, mock_config: Any
    ) -> None:
        """Agent should handle empty tickers list gracefully."""
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value=_mock_llm_response(""))
        with patch("aegis.agents.smart_money_agent.LLMClient", return_value=mock_llm):
            agent = SmartMoneyAgent(memory=mock_memory, tools={}, config=mock_config)
            state = PipelineState(tickers=[])
            result = await agent.run(state)

        assert result.smart_money_data == {}
        assert "smart_money_agent" in result.agent_timings

    @pytest.mark.asyncio
    async def test_run_llm_narrative_failure(
        self, mock_memory: Any, mock_config: Any
    ) -> None:
        """When LLM fails, narrative should be empty string but score still computed."""
        uw_tool = _mock_tool_result(
            True,
            [
                {"type": "call", "strike": 500, "expiration": "2026-07-17", "premium": 200000, "size": 400},
            ],
        )
        oi_tool = _mock_tool_result(
            True,
            {"call_oi_delta": 1000, "put_oi_delta": -500, "oi_delta": 2.0, "daily_oi": []},
        )
        tools = {"unusual_whales": uw_tool, "oi_change": oi_tool}

        with patch("aegis.agents.smart_money_agent.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
            mock_llm_cls.return_value = mock_llm

            agent = SmartMoneyAgent(memory=mock_memory, tools=tools, config=mock_config)
            state = _make_state()
            result = await agent.run(state)

        assert "QQQ" in result.smart_money_data
        data = result.smart_money_data["QQQ"]
        assert data["narrative"] == ""
        assert data["smart_money_score"] > 0  # score still computed

    @pytest.mark.asyncio
    async def test_manifest_correct(self) -> None:
        """Verify manifest fields match design spec."""
        m = SmartMoneyAgent.manifest
        assert m.name == "smart_money_agent"
        assert m.version == "0.1.0"
        assert m.llm_dependency is True
        assert m.parallel_group == "signal_analysts"
        assert m.pipeline_mode == "full"
        assert "smart_money_data" in m.provides
        assert "smart_money" in m.tags
