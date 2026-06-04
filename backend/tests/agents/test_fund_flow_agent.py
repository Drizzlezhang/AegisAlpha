"""Test FundFlowAgent — classification, scoring, narrative, manifest, error handling."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.agents.fund_flow_agent import FundFlowAgent
from aegis.pipeline.state import PipelineState


def _mock_tool_result(success: bool = True, data: Any = None) -> MagicMock:
    result = MagicMock()
    result.success = success
    result.data = data or {}
    return result


# ---------------------------------------------------------------------------
# Classification tests
# ---------------------------------------------------------------------------


class TestLiquidityClassification:
    """Verify _classify_liquidity logic."""

    def test_expanding(self) -> None:
        """ON RRP falling + TGA falling → expanding."""
        rrp = {"observations": [
            {"value": "1000"}, {"value": "1100"},  # ~-9% change
        ]}
        tga = {"observations": [
            {"value": "500"}, {"value": "550"},  # ~-9% change
        ]}
        result = FundFlowAgent._classify_liquidity(rrp, tga)
        assert result == "expanding"

    def test_tightening(self) -> None:
        """ON RRP rising + TGA rising → tightening."""
        rrp = {"observations": [
            {"value": "1100"}, {"value": "1000"},  # +10% change
        ]}
        tga = {"observations": [
            {"value": "550"}, {"value": "500"},  # +10% change
        ]}
        result = FundFlowAgent._classify_liquidity(rrp, tga)
        assert result == "tightening"

    def test_neutral_mixed(self) -> None:
        """Mixed signals → neutral."""
        rrp = {"observations": [
            {"value": "1000"}, {"value": "1100"},  # falling
        ]}
        tga = {"observations": [
            {"value": "550"}, {"value": "500"},  # rising
        ]}
        result = FundFlowAgent._classify_liquidity(rrp, tga)
        assert result == "neutral"

    def test_neutral_insufficient_data(self) -> None:
        """Insufficient data → neutral."""
        result = FundFlowAgent._classify_liquidity({}, {})
        assert result == "neutral"


class TestCreditClassification:
    """Verify _classify_credit logic."""

    def test_risk_on(self) -> None:
        result = FundFlowAgent._classify_credit({"appetite": "risk_on"})
        assert result == "risk_on"

    def test_risk_off(self) -> None:
        result = FundFlowAgent._classify_credit({"appetite": "risk_off"})
        assert result == "risk_off"

    def test_neutral(self) -> None:
        result = FundFlowAgent._classify_credit({"appetite": "neutral"})
        assert result == "neutral"

    def test_empty_data(self) -> None:
        result = FundFlowAgent._classify_credit({})
        assert result == "neutral"


class TestSectorRotation:
    """Verify _sector_rotation logic."""

    def test_rotation_into_out_of(self) -> None:
        flows = {
            "XLK": 1.5e9, "XLY": 1.2e9, "XLI": 0.8e9,
            "XLE": 0.3e9, "XLF": 0.1e9, "XLV": -0.1e9,
            "XBI": -0.2e9, "XLP": -0.5e9, "XLU": -0.8e9, "XLRE": -1.0e9,
        }
        result = FundFlowAgent._sector_rotation(flows)
        assert result["into"] == ["XLK", "XLY", "XLI"]
        assert result["out_of"] == ["XLRE", "XLU", "XLP"]

    def test_empty_flows(self) -> None:
        result = FundFlowAgent._sector_rotation({})
        assert result == {"into": [], "out_of": []}


class TestTickerScoring:
    """Verify _score_for_ticker logic."""

    def test_high_score(self) -> None:
        """Sector in into + expanding → 80+."""
        rotation = {"into": ["XLK"], "out_of": []}
        score = FundFlowAgent._score_for_ticker("AAPL", rotation, "expanding")
        assert score == 85.0

    def test_low_score(self) -> None:
        """Sector in out_of + tightening → 20-."""
        rotation = {"into": [], "out_of": ["XLU"]}
        score = FundFlowAgent._score_for_ticker("DUK", rotation, "tightening")
        # DUK not in map → defaults to SPY, not in into/out_of → base 50 - 15 = 35
        assert score == 35.0

    def test_neutral_score(self) -> None:
        """No rotation match + neutral liquidity → ~50."""
        rotation = {"into": [], "out_of": []}
        score = FundFlowAgent._score_for_ticker("QQQ", rotation, "neutral")
        assert score == 50.0

    def test_score_clamped(self) -> None:
        """Score should be clamped to 0-100."""
        rotation = {"into": ["XLK"], "out_of": []}
        score = FundFlowAgent._score_for_ticker("AAPL", rotation, "expanding")
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# Agent integration tests
# ---------------------------------------------------------------------------


class TestFundFlowAgentRun:
    """Verify FundFlowAgent.run() end-to-end."""

    @pytest.mark.asyncio
    async def test_run_writes_fund_flow_data(
        self, mock_memory: Any, mock_config: Any,
    ) -> None:
        """Should write fund_flow_data and extensions."""
        mock_tools = {
            "etf_flows": AsyncMock(fetch=AsyncMock(return_value=_mock_tool_result(
                True, {"QQQ": {"flow_7d": 2.3e9}, "SPY": {"flow_7d": 1.8e9}}
            ))),
            "sector_etf_flows": AsyncMock(fetch=AsyncMock(return_value=_mock_tool_result(
                True, {"XLK": {"flow_7d": 1.5e9}, "XLY": {"flow_7d": 1.2e9}}
            ))),
            "fred": AsyncMock(fetch=AsyncMock(return_value=_mock_tool_result(
                True, {"observations": [{"value": "1000"}, {"value": "1100"}]}
            ))),
            "hyg_lqd_spread": AsyncMock(fetch=AsyncMock(return_value=_mock_tool_result(
                True, {"appetite": "risk_on", "current_ratio": 0.72}
            ))),
        }

        mock_llm_resp = {
            "content": "Liquidity expanding, risk-on, tech leading.",
            "usage": {"total_tokens": 50},
            "model": "gpt-4o-mini",
        }

        with patch("aegis.agents.fund_flow_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_llm_resp)
            mock_llm_cls.return_value = mock_llm

            agent = FundFlowAgent(
                memory=mock_memory, tools=mock_tools, config=mock_config
            )
            state = PipelineState(tickers=["QQQ"])
            result = await agent.run(state)

        assert "QQQ" in result.fund_flow_data
        assert result.fund_flow_data["QQQ"]["fund_flow_score"] > 0
        ext = result.extensions.get("fund_flow_agent", {})
        assert "macro_liquidity" in ext
        assert "credit_appetite" in ext
        assert "narrative" in ext
        assert "fund_flow_agent" in result.agent_timings

    @pytest.mark.asyncio
    async def test_run_tool_failure_graceful(
        self, mock_memory: Any, mock_config: Any,
    ) -> None:
        """Should continue when all tools fail."""
        mock_tools = {
            "etf_flows": AsyncMock(fetch=AsyncMock(
                side_effect=Exception("Connection error")
            )),
            "sector_etf_flows": AsyncMock(fetch=AsyncMock(
                side_effect=Exception("Timeout")
            )),
            "fred": AsyncMock(fetch=AsyncMock(
                side_effect=Exception("API error")
            )),
            "hyg_lqd_spread": AsyncMock(fetch=AsyncMock(
                side_effect=Exception("Data error")
            )),
        }

        mock_llm_resp = {
            "content": "Data unavailable.",
            "usage": {"total_tokens": 10},
            "model": "gpt-4o-mini",
        }

        with patch("aegis.agents.fund_flow_agent.LLMClient") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_llm.chat = AsyncMock(return_value=mock_llm_resp)
            mock_llm_cls.return_value = mock_llm

            agent = FundFlowAgent(
                memory=mock_memory, tools=mock_tools, config=mock_config
            )
            state = PipelineState(tickers=["QQQ"])
            result = await agent.run(state)

        # Should still complete with neutral defaults
        ext = result.extensions.get("fund_flow_agent", {})
        assert ext.get("macro_liquidity") == "neutral"
        assert ext.get("credit_appetite") == "neutral"

    @pytest.mark.asyncio
    async def test_manifest_fields(self) -> None:
        """Manifest should have correct fields."""
        m = FundFlowAgent.manifest
        assert m.name == "fund_flow_agent"
        assert m.llm_dependency is True
        assert m.parallel_group == "signal_analysts"
        assert m.pipeline_mode == "full"
        assert "signal" in m.tags
        assert "macro_flow" in m.tags

    @pytest.mark.asyncio
    async def test_fallback_narrative(self) -> None:
        """Fallback narrative should produce non-empty string."""
        narrative = FundFlowAgent._fallback_narrative(
            "expanding", "risk_on",
            {"into": ["XLK"], "out_of": ["XLU"]},
        )
        assert "expanding" in narrative
        assert "risk_on" in narrative
        assert "XLK" in narrative
