"""Test ResearchManagerAgent — ranking, pending_triggers, LLM failure, manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from aegis.agents.research_manager_agent import ResearchManagerAgent
from aegis.pipeline.state import PipelineState, Recommendation

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
        assert "triggers" in m.tags


# ---------------------------------------------------------------------------
# M2 v1.3 new tests
# ---------------------------------------------------------------------------


class TestResearchManagerV2:
    """Tests for Research Manager v2 features."""

    # ------------------------------------------------------------------
    # Right-side confirmation
    # ------------------------------------------------------------------

    def test_right_side_confirmed_passes_with_volume(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should pass when volume > 1.5× average and low retrace."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": {"volume": 2000000, "avg_volume_20d": 1000000, "retrace_from_breakout_pct": 0.20}},
            positions={},
            debate_results={},
            options_step2={},
        )
        assert agent._right_side_confirmed(state, "QQQ") is True

    def test_right_side_confirmed_fails_low_volume(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should fail when volume < 1.5× average."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": {"volume": 1000000, "avg_volume_20d": 1000000, "retrace_from_breakout_pct": 0.20}},
            positions={},
            debate_results={},
            options_step2={},
        )
        assert agent._right_side_confirmed(state, "QQQ") is False

    def test_right_side_confirmed_fails_high_retrace(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should fail when retrace > 50%."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState(
            tickers=["QQQ"],
            market_data={"QQQ": {"volume": 2000000, "avg_volume_20d": 1000000, "retrace_from_breakout_pct": 0.60}},
            positions={},
            debate_results={},
            options_step2={},
        )
        assert agent._right_side_confirmed(state, "QQQ") is False

    # ------------------------------------------------------------------
    # Add-on evaluation
    # ------------------------------------------------------------------

    def test_build_add_recommendations_generates_add_on(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should generate add-on when position < 20% and thesis strengthening."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState(
            tickers=["QQQ"],
            positions={
                "total_nav": 100000.0,
                "holdings": [{"ticker": "QQQ", "position_pct": 0.10, "strategy": "leaps_call", "prev_debate_score": 0.60}],
            },
            entry_mode={"QQQ": "active_left"},
            debate_results={"QQQ": {"direction": "bullish", "confidence": 0.80}},
            options_step2={},
        )
        recs = agent._build_add_recommendations(state)
        assert len(recs) == 1
        assert recs[0].action == "add"
        assert recs[0].ticker == "QQQ"

    def test_build_add_recommendations_skips_passive(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should skip passive positions."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState(
            tickers=["QQQ"],
            positions={
                "total_nav": 100000.0,
                "holdings": [{"ticker": "QQQ", "position_pct": 0.10, "strategy": "stock", "prev_debate_score": 0.60}],
            },
            entry_mode={"QQQ": "passive"},
            debate_results={"QQQ": {"direction": "bullish", "confidence": 0.80}},
            options_step2={},
        )
        recs = agent._build_add_recommendations(state)
        assert len(recs) == 0

    def test_build_add_recommendations_skips_full_position(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should skip positions already at 20%+."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState(
            tickers=["QQQ"],
            positions={
                "total_nav": 100000.0,
                "holdings": [{"ticker": "QQQ", "position_pct": 0.25, "strategy": "leaps_call", "prev_debate_score": 0.60}],
            },
            entry_mode={"QQQ": "active_left"},
            debate_results={"QQQ": {"direction": "bullish", "confidence": 0.80}},
            options_step2={},
        )
        recs = agent._build_add_recommendations(state)
        assert len(recs) == 0

    # ------------------------------------------------------------------
    # Cooldown
    # ------------------------------------------------------------------

    def test_in_cooldown_blocks_recent_close(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should return True for ticker closed within cooldown period."""
        from datetime import datetime, timedelta, timezone

        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        recent = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        state = PipelineState(
            tickers=["QQQ"],
            positions={"closed_positions": [{"ticker": "QQQ", "closed_at": recent}]},
            debate_results={"QQQ": {"direction": "bullish", "confidence": 0.60}},
            options_step2={},
        )
        assert agent._in_cooldown(state, "QQQ") is True

    def test_in_cooldown_overridden_by_strong_reversal(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Strong reversal signal should override cooldown."""
        from datetime import datetime, timedelta, timezone

        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        recent = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        state = PipelineState(
            tickers=["QQQ"],
            positions={"closed_positions": [{"ticker": "QQQ", "closed_at": recent}]},
            debate_results={"QQQ": {"direction": "reversal", "confidence": 0.85}},
            options_step2={},
        )
        assert agent._in_cooldown(state, "QQQ") is False

    def test_in_cooldown_allows_old_close(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should return False for ticker closed beyond cooldown period."""
        from datetime import datetime, timedelta, timezone

        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        state = PipelineState(
            tickers=["QQQ"],
            positions={"closed_positions": [{"ticker": "QQQ", "closed_at": old}]},
            debate_results={},
            options_step2={},
        )
        assert agent._in_cooldown(state, "QQQ") is False

    # ------------------------------------------------------------------
    # Trigger extraction
    # ------------------------------------------------------------------

    def test_extract_triggers_active_left(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should generate price_below trigger for active_left."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState(
            tickers=["QQQ"],
            options_step2={"QQQ": {"entry_mode": "active_left"}},
            analyst_outputs={"levels": {"QQQ": {"support_levels": [400.0]}}},
            market_data={"QQQ": {"rsi_14": 50}},
            positions={},
            debate_results={},
        )
        triggers = agent._extract_triggers(state)
        assert len(triggers) >= 1
        price_triggers = [t for t in triggers if t["trigger_type"] == "price_below"]
        assert len(price_triggers) == 1
        assert price_triggers[0]["trigger_params"]["threshold"] == 400.0

    def test_extract_triggers_active_right(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should generate price_above trigger for active_right."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState(
            tickers=["QQQ"],
            options_step2={"QQQ": {"entry_mode": "active_right"}},
            analyst_outputs={"levels": {"QQQ": {"resistance_levels": [480.0]}}},
            market_data={"QQQ": {"rsi_14": 50}},
            positions={},
            debate_results={},
        )
        triggers = agent._extract_triggers(state)
        price_triggers = [t for t in triggers if t["trigger_type"] == "price_above"]
        assert len(price_triggers) == 1
        assert price_triggers[0]["trigger_params"]["threshold"] == 480.0

    def test_extract_triggers_rsi_oversold(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should generate rsi_below trigger when RSI < 30."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState(
            tickers=["QQQ"],
            options_step2={"QQQ": {"entry_mode": "both"}},
            analyst_outputs={"levels": {}},
            market_data={"QQQ": {"rsi_14": 25}},
            positions={},
            debate_results={},
        )
        triggers = agent._extract_triggers(state)
        rsi_triggers = [t for t in triggers if t["trigger_type"] == "rsi_below"]
        assert len(rsi_triggers) == 1

    # ------------------------------------------------------------------
    # CC Timing Guard
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_cc_timing_generates_when_conditions_met(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should generate CC recommendation when ranging + resistance + high IV."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState(
            tickers=["QQQ"],
            entry_mode={"QQQ": "cc"},
            analyst_outputs={
                "trend": {"QQQ": {"phase": "ranging"}},
                "levels": {"QQQ": {"resistance_levels": [480.0]}},
            },
            options_step1={"QQQ": {"iv_data": {"percentile": 0.75}}},
            positions={},
            debate_results={},
        )
        recs = await agent._cc_timing(state)
        assert len(recs) == 1
        assert recs[0].strategy == "covered_call"
        assert recs[0].action == "sell"

    @pytest.mark.asyncio
    async def test_cc_timing_skips_when_trending(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should skip CC when market is trending (not ranging)."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState(
            tickers=["QQQ"],
            entry_mode={"QQQ": "cc"},
            analyst_outputs={
                "trend": {"QQQ": {"phase": "markup"}},
                "levels": {"QQQ": {"resistance_levels": [480.0]}},
            },
            options_step1={"QQQ": {"iv_data": {"percentile": 0.75}}},
            positions={},
            debate_results={},
        )
        recs = await agent._cc_timing(state)
        assert len(recs) == 0

    @pytest.mark.asyncio
    async def test_cc_timing_skips_when_low_iv(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should skip CC when IV is not elevated."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState(
            tickers=["QQQ"],
            entry_mode={"QQQ": "cc"},
            analyst_outputs={
                "trend": {"QQQ": {"phase": "ranging"}},
                "levels": {"QQQ": {"resistance_levels": [480.0]}},
            },
            options_step1={"QQQ": {"iv_data": {"percentile": 0.30}}},
            positions={},
            debate_results={},
        )
        recs = await agent._cc_timing(state)
        assert len(recs) == 0

    # ------------------------------------------------------------------
    # Ranking and cap
    # ------------------------------------------------------------------

    def test_rank_and_cap_sorts_by_urgency_then_score(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should sort by urgency weight × score, then cap."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        recs = [
            Recommendation(ticker="A", action="buy", strategy="stock", rationale="", urgency="low", score=90, delta_dollars_delta=100),
            Recommendation(ticker="B", action="buy", strategy="stock", rationale="", urgency="high", score=70, delta_dollars_delta=200),
            Recommendation(ticker="C", action="buy", strategy="stock", rationale="", urgency="medium", score=80, delta_dollars_delta=150),
        ]
        result = agent._rank_and_cap(recs)
        # high×70=210 > medium×80=160 > low×90=90
        assert result[0].ticker == "B"
        assert result[1].ticker == "C"
        assert result[2].ticker == "A"

    def test_rank_and_cap_enforces_daily_limit(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        """Should cap at max_daily_recommendations."""
        with patch("aegis.agents.research_manager_agent.LLMClient"):
            agent = ResearchManagerAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        agent._max_daily = 2
        recs = [
            Recommendation(ticker="A", action="buy", strategy="stock", rationale="", urgency="high", score=90, delta_dollars_delta=100),
            Recommendation(ticker="B", action="buy", strategy="stock", rationale="", urgency="high", score=80, delta_dollars_delta=100),
            Recommendation(ticker="C", action="buy", strategy="stock", rationale="", urgency="high", score=70, delta_dollars_delta=100),
        ]
        result = agent._rank_and_cap(recs)
        assert len(result) == 2
