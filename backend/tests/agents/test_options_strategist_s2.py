"""Test OptionsStrategistS2Agent — M2 v1.3: entry_mode, multi-strategy, scenario PnL, roll, batch, stop-loss."""

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


def _make_candidate(**overrides: Any) -> dict[str, Any]:
    base = {
        "strike": 450.0,
        "type": "call",
        "dte": 400,
        "delta": 0.6,
        "gamma": 0.02,
        "theta": -0.05,
        "vega": 0.15,
        "iv": 0.25,
        "bid": 22.0,
        "ask": 23.0,
        "oi": 500,
        "spot_price": 450.0,
        "expiration": "2027-06-01",
    }
    base.update(overrides)
    return base


class TestOptionsStrategistS2:
    # ------------------------------------------------------------------
    # Existing tests — updated for M2 v1.3 output structure
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_generates_plans_with_support_based_stop(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Plans should have support_based stop_loss when active_left (near support)."""
        mock_response = _llm_response(
            [{"strike": 410.0, "type": "call", "entry_price": 12.50, "rationale": "near support", "entry_mode": "active_left"}]
        )
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            # spot=410, support=400 → distance 2.4% < 3% → active_left
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [_make_candidate(strike=410.0, spot_price=410.0)]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.60, "rationale": "near support reversal"}},
                analyst_outputs={"levels": {"QQQ": {"support_levels": [400.0], "resistance_levels": [480.0]}}},
            )
            result = await agent.run(state)
            output = result.options_step2["QQQ"]
            assert "contracts" in output
            assert "plans" in output
            assert len(output["plans"]) >= 1
            plan = output["plans"][0]
            assert "stop_loss_plan" in plan
            assert plan["stop_loss_plan"]["mode"] == "support_based"

    @pytest.mark.asyncio
    async def test_falls_back_to_fixed_pct_when_no_levels(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should use fixed_pct stop_loss when no support levels available."""
        mock_response = _llm_response(
            [{"strike": 450.0, "type": "call", "entry_price": 22.50, "rationale": "momentum play", "entry_mode": "passive"}]
        )
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [_make_candidate()]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.85, "rationale": "momentum"}},
                analyst_outputs={"levels": {"QQQ": {"support_levels": [], "resistance_levels": []}}},
            )
            result = await agent.run(state)
            plan = result.options_step2["QQQ"]["plans"][0]
            assert plan["stop_loss_plan"]["mode"] == "fixed_pct"

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
                options_step1={"QQQ": {"candidates": [_make_candidate()]}},
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
                options_step1={"QQQ": {"candidates": [_make_candidate()]}},
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
        mock_response = _llm_response(
            [{"strike": 450.0, "type": "call", "entry_price": 22.50, "rationale": "test", "entry_mode": "passive"}]
        )
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [_make_candidate()]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.85, "rationale": "test"}},
                analyst_outputs={"levels": {"QQQ": {"support_levels": [400.0], "resistance_levels": []}}},
            )
            result = await agent.run(state)
            assert "options_strategist_s2" in result.extensions
            ext = result.extensions["options_strategist_s2"]
            assert "s2_raw" in ext
            assert ext["s2_raw"]["contracts_count"] == 1
            assert "entry_mode" in ext["s2_raw"]

    def test_manifest_compliance(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient"):
            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
        m = agent.manifest
        assert m.name == "options_strategist_s2"
        assert m.llm_dependency is True
        assert m.pipeline_mode == "full"
        assert "options" in m.tags
        assert "strategy" in m.tags
        assert "multi_strategy" in m.tags

    # ------------------------------------------------------------------
    # M2 v1.3 new tests — entry_mode
    # ------------------------------------------------------------------

    def test_decide_entry_mode_active_left_near_support(self) -> None:
        """Should return active_left when bullish + near support."""
        debate = {"direction": "bullish", "confidence": 0.6}
        levels = {"support_levels": [440.0]}
        candidates = [_make_candidate(spot_price=450.0)]  # 2.2% from support
        result = OptionsStrategistS2Agent._decide_entry_mode(debate, levels, candidates)
        assert result == "active_left"

    def test_decide_entry_mode_active_right_breakout(self) -> None:
        """Should return active_right when breakout + high confidence."""
        debate = {"direction": "breakout", "confidence": 0.85}
        levels = {"support_levels": [400.0]}
        candidates = [_make_candidate(spot_price=480.0)]  # far from support
        result = OptionsStrategistS2Agent._decide_entry_mode(debate, levels, candidates)
        assert result == "active_right"

    def test_decide_entry_mode_both_when_ambiguous(self) -> None:
        """Should return both when direction unclear."""
        debate = {"direction": "neutral", "confidence": 0.5}
        levels = {}
        candidates = [_make_candidate()]
        result = OptionsStrategistS2Agent._decide_entry_mode(debate, levels, candidates)
        assert result == "both"

    def test_decide_entry_mode_both_when_both_eligible(self) -> None:
        """Should return both when both left and right conditions met."""
        debate = {"direction": "bullish", "confidence": 0.85}
        levels = {"support_levels": [440.0]}
        candidates = [_make_candidate(spot_price=450.0)]  # near support + high confidence
        result = OptionsStrategistS2Agent._decide_entry_mode(debate, levels, candidates)
        assert result == "both"

    # ------------------------------------------------------------------
    # M2 v1.3 new tests — multi-strategy
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_generates_at_least_two_plans(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should generate >= 2 plans per ticker."""
        mock_response = _llm_response(
            [{"strike": 450.0, "type": "call", "entry_price": 22.50, "rationale": "test", "entry_mode": "passive"}]
        )
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [_make_candidate(), _make_candidate(strike=460.0)]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.85, "rationale": "test"}},
                analyst_outputs={"levels": {"QQQ": {"support_levels": [400.0], "resistance_levels": []}}},
            )
            result = await agent.run(state)
            plans = result.options_step2["QQQ"]["plans"]
            assert len(plans) >= 2

    @pytest.mark.asyncio
    async def test_plans_have_required_fields(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Each plan should have strategy, pros, cons, liquidity_score."""
        mock_response = _llm_response(
            [{"strike": 450.0, "type": "call", "entry_price": 22.50, "rationale": "test", "entry_mode": "passive"}]
        )
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [_make_candidate()]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.85, "rationale": "test"}},
                analyst_outputs={"levels": {"QQQ": {"support_levels": [400.0], "resistance_levels": []}}},
            )
            result = await agent.run(state)
            for plan in result.options_step2["QQQ"]["plans"]:
                assert "strategy" in plan
                assert "pros" in plan
                assert "cons" in plan
                assert "liquidity_score" in plan
                assert "scenario_pnl" in plan
                assert "entry_mode" in plan

    # ------------------------------------------------------------------
    # M2 v1.3 new tests — scenario P&L
    # ------------------------------------------------------------------

    def test_compute_scenario_pnl_has_all_scenarios(self) -> None:
        """Scenario P&L should have target, flat_30d, flat_60d, flat_90d, stop_loss."""
        from aegis.pipeline.state import OptionPlan

        plan = OptionPlan(
            plan_no=1,
            strategy="leaps_call",
            strike=450.0,
            expiry="2027-06-01",
            dte=400,
            option_type="call",
            delta=0.6,
            gamma=0.02,
            theta=-0.05,
            vega=0.15,
            iv=0.25,
            estimated_cost=2250.0,
            entry_mode="active_left",
        )
        result = OptionsStrategistS2Agent.compute_scenario_pnl(plan, 450.0)
        assert "target" in result.model_dump()
        assert "flat_30d" in result.model_dump()
        assert "flat_60d" in result.model_dump()
        assert "flat_90d" in result.model_dump()
        assert "stop_loss" in result.model_dump()
        # Target should be above entry
        assert result.target["price"] > 450.0
        # Stop loss should be below entry
        assert result.stop_loss["price"] < 450.0

    # ------------------------------------------------------------------
    # M2 v1.3 new tests — roll evaluation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_roll_evaluation_qqq_close_only(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """QQQ LEAPS should return close_only, never roll."""
        mock_response = _llm_response(
            [{"strike": 450.0, "type": "call", "entry_price": 22.50, "rationale": "test", "entry_mode": "passive"}]
        )
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [_make_candidate()]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.85, "rationale": "test"}},
                analyst_outputs={"levels": {"QQQ": {"support_levels": [400.0], "resistance_levels": []}}},
                positions={"QQQ": {"dte": 150, "type": "leaps_call"}},
            )
            result = await agent.run(state)
            roll = result.options_step2["QQQ"]["roll_evaluation"]
            assert roll is not None
            assert roll["action"] == "close_only"

    @pytest.mark.asyncio
    async def test_roll_evaluation_non_qqq_roll(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Non-QQQ LEAPS with low DTE should suggest roll."""
        mock_response = _llm_response(
            [{"strike": 200.0, "type": "call", "entry_price": 15.0, "rationale": "test", "entry_mode": "passive"}]
        )
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["AAPL"],
                options_step1={"AAPL": {"candidates": [_make_candidate(strike=200.0, spot_price=200.0)]}},
                debate_results={"AAPL": {"direction": "bullish", "confidence": 0.85, "rationale": "test"}},
                analyst_outputs={"levels": {"AAPL": {"support_levels": [180.0], "resistance_levels": []}}},
                positions={"AAPL": {"dte": 150, "type": "leaps_call"}},
            )
            result = await agent.run(state)
            roll = result.options_step2["AAPL"]["roll_evaluation"]
            assert roll is not None
            assert roll["action"] == "roll"

    @pytest.mark.asyncio
    async def test_roll_evaluation_no_positions(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """No positions should return None for roll evaluation."""
        mock_response = _llm_response(
            [{"strike": 450.0, "type": "call", "entry_price": 22.50, "rationale": "test", "entry_mode": "passive"}]
        )
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [_make_candidate()]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.85, "rationale": "test"}},
                analyst_outputs={"levels": {"QQQ": {"support_levels": [400.0], "resistance_levels": []}}},
                positions={},
            )
            result = await agent.run(state)
            assert result.options_step2["QQQ"]["roll_evaluation"] is None

    # ------------------------------------------------------------------
    # M2 v1.3 new tests — batch entry
    # ------------------------------------------------------------------

    def test_batch_entry_splits_active_left(self) -> None:
        """active_left plans should be split into 3 batches."""
        from aegis.pipeline.state import OptionPlan

        plan = OptionPlan(
            plan_no=1,
            strategy="leaps_call",
            strike=450.0,
            expiry="2027-06-01",
            dte=400,
            option_type="call",
            delta=0.6,
            gamma=0.02,
            theta=-0.05,
            vega=0.15,
            iv=0.25,
            estimated_cost=2250.0,
            entry_mode="active_left",
        )
        levels = {"support_levels": [400.0]}
        result = OptionsStrategistS2Agent._add_batch_entry([plan], levels)
        assert len(result) == 3
        assert result[0].batch_no == 1
        assert result[1].batch_no == 2
        assert result[2].batch_no == 3
        assert result[1].batch_trigger_price == 400.0
        assert result[2].batch_trigger_price == pytest.approx(392.0)

    def test_batch_entry_no_support_levels(self) -> None:
        """No support levels should return plans unchanged."""
        from aegis.pipeline.state import OptionPlan

        plan = OptionPlan(
            plan_no=1,
            strategy="leaps_call",
            strike=450.0,
            expiry="2027-06-01",
            dte=400,
            option_type="call",
            delta=0.6,
            gamma=0.02,
            theta=-0.05,
            vega=0.15,
            iv=0.25,
            estimated_cost=2250.0,
            entry_mode="active_left",
        )
        result = OptionsStrategistS2Agent._add_batch_entry([plan], {})
        assert len(result) == 1

    def test_batch_entry_non_left_mode_unchanged(self) -> None:
        """active_right plans should not be split."""
        from aegis.pipeline.state import OptionPlan

        plan = OptionPlan(
            plan_no=1,
            strategy="leaps_call",
            strike=450.0,
            expiry="2027-06-01",
            dte=400,
            option_type="call",
            delta=0.6,
            gamma=0.02,
            theta=-0.05,
            vega=0.15,
            iv=0.25,
            estimated_cost=2250.0,
            entry_mode="active_right",
        )
        levels = {"support_levels": [400.0]}
        result = OptionsStrategistS2Agent._add_batch_entry([plan], levels)
        assert len(result) == 1

    # ------------------------------------------------------------------
    # M2 v1.3 new tests — stop-loss plan
    # ------------------------------------------------------------------

    def test_build_stop_loss_active_left_support_based(self) -> None:
        """active_left should use support_based stop loss."""
        levels = {"support_levels": [400.0]}
        result = OptionsStrategistS2Agent._build_stop_loss("active_left", levels, 450.0)
        assert result["mode"] == "support_based"
        assert "trigger_price" in result
        assert result["support_level"] == 400.0

    def test_build_stop_loss_active_right_fixed_pct(self) -> None:
        """active_right should use fixed_pct stop loss."""
        result = OptionsStrategistS2Agent._build_stop_loss("active_right", {}, 450.0)
        assert result["mode"] == "fixed_pct"
        assert "trigger_price" in result
        assert result["drop_pct_from_entry"] is not None

    # ------------------------------------------------------------------
    # M2 v1.3 new tests — strategy_comparisons + scenario_pnl on state
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_writes_strategy_comparisons_to_state(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Should write strategy_comparisons and scenario_pnl to state."""
        mock_response = _llm_response(
            [{"strike": 450.0, "type": "call", "entry_price": 22.50, "rationale": "test", "entry_mode": "passive"}]
        )
        with patch("aegis.agents.options_strategist_s2_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_llm_cls.return_value = mock_llm

            agent = OptionsStrategistS2Agent(memory=mock_memory, tools=mock_tools, config=mock_config)
            state = PipelineState(
                tickers=["QQQ"],
                options_step1={"QQQ": {"candidates": [_make_candidate()]}},
                debate_results={"QQQ": {"direction": "bullish", "confidence": 0.85, "rationale": "test"}},
                analyst_outputs={"levels": {"QQQ": {"support_levels": [400.0], "resistance_levels": []}}},
            )
            result = await agent.run(state)
            assert "QQQ" in result.strategy_comparisons
            assert len(result.strategy_comparisons["QQQ"]) >= 1
            assert "QQQ" in result.scenario_pnl
            assert "plan_1" in result.scenario_pnl["QQQ"]
