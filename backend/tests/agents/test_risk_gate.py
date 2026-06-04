"""Test RiskGateAgent — 8 rules + all-pass + boundary + support_based missing."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from aegis.agents.risk_gate_agent import RiskGateAgent
from aegis.pipeline.state import PipelineState, Recommendation

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def _make_rec(**overrides: Any) -> Recommendation:
    defaults: dict[str, Any] = {
        "ticker": "QQQ",
        "action": "buy",
        "strategy": "leaps_call",
        "rationale": "test recommendation",
        "urgency": "high",
        "score": 80.0,
        "delta_dollars_delta": 500.0,
    }
    defaults.update(overrides)
    return Recommendation(**defaults)


def _make_state(**overrides: Any) -> PipelineState:
    defaults: dict[str, Any] = {
        "tickers": ["QQQ"],
        "positions": {
            "total_nav": 100000.0,
            "cash": 50000.0,
            "total_position_pct": 0.50,
            "holdings": [{"ticker": "QQQ", "shares": 100, "avg_cost": 400.0}],
        },
        "market_data": {
            "QQQ": {"vix": 18.0, "vix_daily_change_pct": 0.02, "price": 420.0},
        },
        "macro_data": {"fomc_meeting": None, "next_earnings": {}},
        "entry_mode": {},
    }
    defaults.update(overrides)
    return PipelineState(**defaults)


@pytest.fixture
def agent(mock_memory: Any, mock_tools: Any, mock_config: Any) -> RiskGateAgent:
    return RiskGateAgent(memory=mock_memory, tools=mock_tools, config=mock_config)


# ---------------------------------------------------------------------------
# Rule 1: Position limit
# ---------------------------------------------------------------------------


class TestPositionLimit:
    @pytest.mark.asyncio
    async def test_blocks_when_over_80pct(self, agent: RiskGateAgent) -> None:
        rec = _make_rec(action="buy")
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 10000.0,
                "total_position_pct": 0.85,
                "holdings": [],
            }
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 0
        assert len(result.blocked_recommendations) == 1
        assert "Position limit" in result.blocked_recommendations[0].block_reason

    @pytest.mark.asyncio
    async def test_allows_at_80pct_boundary(self, agent: RiskGateAgent) -> None:
        """80% exactly should pass (rule is > 80%, not >=)."""
        rec = _make_rec(action="buy")
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 20000.0,
                "total_position_pct": 0.80,
                "holdings": [],
            }
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1
        assert len(result.blocked_recommendations) == 0

    @pytest.mark.asyncio
    async def test_skips_for_hold_action(self, agent: RiskGateAgent) -> None:
        """Position limit only applies to buy/add, not hold."""
        rec = _make_rec(action="hold")
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 10000.0,
                "total_position_pct": 0.85,
                "holdings": [],
            }
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1


# ---------------------------------------------------------------------------
# Rule 2: Cash minimum
# ---------------------------------------------------------------------------


class TestCashMinimum:
    @pytest.mark.asyncio
    async def test_blocks_when_cash_below_20pct(self, agent: RiskGateAgent) -> None:
        rec = _make_rec(action="buy")
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 10000.0,
                "total_position_pct": 0.50,
                "holdings": [],
            }
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 0
        assert len(result.blocked_recommendations) == 1
        assert "Cash below" in result.blocked_recommendations[0].block_reason

    @pytest.mark.asyncio
    async def test_allows_when_cash_sufficient(self, agent: RiskGateAgent) -> None:
        rec = _make_rec(action="buy")
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 30000.0,
                "total_position_pct": 0.50,
                "holdings": [],
            }
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1


# ---------------------------------------------------------------------------
# Rule 3: Blacklist
# ---------------------------------------------------------------------------


class TestBlacklist:
    @pytest.mark.asyncio
    async def test_blocks_blacklisted_ticker(self, agent: RiskGateAgent) -> None:
        agent._rules["blacklist_tickers"] = ["GME"]
        rec = _make_rec(ticker="GME", action="buy")
        state = _make_state()
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 0
        assert len(result.blocked_recommendations) == 1
        assert "blacklisted" in result.blocked_recommendations[0].block_reason

    @pytest.mark.asyncio
    async def test_allows_non_blacklisted(self, agent: RiskGateAgent) -> None:
        agent._rules["blacklist_tickers"] = ["GME"]
        rec = _make_rec(ticker="QQQ", action="buy")
        state = _make_state()
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1


# ---------------------------------------------------------------------------
# Rule 4: LEAPS DTE
# ---------------------------------------------------------------------------


class TestLeapsDTE:
    @pytest.mark.asyncio
    async def test_blocks_short_dte_leaps(self, agent: RiskGateAgent) -> None:
        from aegis.pipeline.state import OptionContract

        rec = _make_rec(
            action="buy",
            strategy="leaps_call",
            option_contracts=[
                OptionContract(
                    symbol="QQQ250117C00450000",
                    type="call",
                    strike=450.0,
                    expiration="2025-01-17",
                    dte=200,
                    bid=10.0,
                    ask=11.0,
                    delta=0.6,
                    gamma=0.01,
                    theta=-0.05,
                    vega=0.2,
                    iv=0.25,
                )
            ],
        )
        state = _make_state()
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 0
        assert len(result.blocked_recommendations) == 1
        assert "DTE too short" in result.blocked_recommendations[0].block_reason

    @pytest.mark.asyncio
    async def test_allows_sufficient_dte_leaps(self, agent: RiskGateAgent) -> None:
        from aegis.pipeline.state import OptionContract

        rec = _make_rec(
            action="buy",
            strategy="leaps_call",
            option_contracts=[
                OptionContract(
                    symbol="QQQ270117C00450000",
                    type="call",
                    strike=450.0,
                    expiration="2027-01-17",
                    dte=400,
                    bid=22.0,
                    ask=23.0,
                    delta=0.6,
                    gamma=0.01,
                    theta=-0.05,
                    vega=0.2,
                    iv=0.25,
                )
            ],
        )
        state = _make_state()
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1

    @pytest.mark.asyncio
    async def test_skips_non_leaps_strategy(self, agent: RiskGateAgent) -> None:
        """DTE check only applies to leaps_call strategy."""
        rec = _make_rec(action="buy", strategy="stock")
        state = _make_state()
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1


# ---------------------------------------------------------------------------
# Rule 5: VIX
# ---------------------------------------------------------------------------


class TestVIX:
    @pytest.mark.asyncio
    async def test_blocks_vix_spike(self, agent: RiskGateAgent) -> None:
        fixture = _load_fixture("risk_gate_vix_spike.json")
        rec = _make_rec(action="buy")
        state = _make_state(
            market_data=fixture["market_data"],
            macro_data=fixture["macro_data"],
            positions=fixture["positions"],
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 0
        assert len(result.blocked_recommendations) == 1
        assert "VIX too high" in result.blocked_recommendations[0].block_reason

    @pytest.mark.asyncio
    async def test_blocks_vix_daily_spike(self, agent: RiskGateAgent) -> None:
        rec = _make_rec(action="buy")
        state = _make_state(
            market_data={
                "QQQ": {"vix": 25.0, "vix_daily_change_pct": 0.25, "price": 420.0},
            }
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 0
        assert "VIX daily spike" in result.blocked_recommendations[0].block_reason

    @pytest.mark.asyncio
    async def test_allows_normal_vix(self, agent: RiskGateAgent) -> None:
        rec = _make_rec(action="buy")
        state = _make_state()
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1


# ---------------------------------------------------------------------------
# Rule 6: FOMC blackout
# ---------------------------------------------------------------------------


class TestFOMCBlackout:
    @pytest.mark.asyncio
    async def test_blocks_leaps_during_fomc_blackout(self, agent: RiskGateAgent) -> None:
        fomc_time = datetime.now(UTC) + timedelta(hours=12)
        rec = _make_rec(action="buy", strategy="leaps_call")
        state = _make_state(
            macro_data={
                "fomc_meeting": fomc_time.isoformat(),
                "next_earnings": {},
            }
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 0
        assert len(result.blocked_recommendations) == 1
        assert "FOMC blackout" in result.blocked_recommendations[0].block_reason

    @pytest.mark.asyncio
    async def test_allows_non_leaps_during_fomc(self, agent: RiskGateAgent) -> None:
        fomc_time = datetime.now(UTC) + timedelta(hours=12)
        rec = _make_rec(action="buy", strategy="stock")
        state = _make_state(
            macro_data={
                "fomc_meeting": fomc_time.isoformat(),
                "next_earnings": {},
            }
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1

    @pytest.mark.asyncio
    async def test_allows_when_no_fomc(self, agent: RiskGateAgent) -> None:
        rec = _make_rec(action="buy", strategy="leaps_call")
        state = _make_state()
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1


# ---------------------------------------------------------------------------
# Rule 7: Earnings blackout
# ---------------------------------------------------------------------------


class TestEarningsBlackout:
    @pytest.mark.asyncio
    async def test_blocks_during_earnings_blackout(self, agent: RiskGateAgent) -> None:
        fixture = _load_fixture("risk_gate_earnings_upcoming.json")
        rec = _make_rec(action="buy", ticker="QQQ")
        state = _make_state(
            market_data=fixture["market_data"],
            macro_data=fixture["macro_data"],
            positions=fixture["positions"],
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 0
        assert len(result.blocked_recommendations) == 1
        assert "Earnings blackout" in result.blocked_recommendations[0].block_reason

    @pytest.mark.asyncio
    async def test_allows_different_ticker_during_earnings(self, agent: RiskGateAgent) -> None:
        """Earnings blackout for QQQ should not block SPY."""
        fixture = _load_fixture("risk_gate_earnings_upcoming.json")
        rec = _make_rec(action="buy", ticker="SPY")
        state = _make_state(
            market_data={"SPY": fixture["market_data"]["QQQ"]},
            macro_data=fixture["macro_data"],
            positions=fixture["positions"],
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1


# ---------------------------------------------------------------------------
# Rule 8: Support-based stop loss
# ---------------------------------------------------------------------------


class TestSupportBasedStopLoss:
    @pytest.mark.asyncio
    async def test_blocks_active_left_without_support_stop(self, agent: RiskGateAgent) -> None:
        rec = _make_rec(action="buy", stop_loss={})
        state = _make_state(entry_mode={"QQQ": "active_left"})
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 0
        assert len(result.blocked_recommendations) == 1
        assert "Support-based stop loss" in result.blocked_recommendations[0].block_reason

    @pytest.mark.asyncio
    async def test_allows_active_left_with_support_stop(self, agent: RiskGateAgent) -> None:
        rec = _make_rec(
            action="buy",
            stop_loss={"method": "support_based", "stop_price": 380.0, "pct": 0.05},
        )
        state = _make_state(entry_mode={"QQQ": "active_left"})
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1

    @pytest.mark.asyncio
    async def test_skips_for_non_active_left(self, agent: RiskGateAgent) -> None:
        """Support-based stop loss only required for active_left."""
        rec = _make_rec(action="buy", stop_loss={})
        state = _make_state(entry_mode={"QQQ": "active_right"})
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1


# ---------------------------------------------------------------------------
# All-pass scenario
# ---------------------------------------------------------------------------


class TestAllPass:
    @pytest.mark.asyncio
    async def test_all_recommendations_pass(self, agent: RiskGateAgent) -> None:
        rec1 = _make_rec(action="buy", strategy="stock", ticker="QQQ")
        rec2 = _make_rec(action="hold", strategy="stock", ticker="SPY")
        state = _make_state()
        state.recommendations = [rec1, rec2]
        result = await agent.run(state)
        assert len(result.recommendations) == 2
        assert len(result.blocked_recommendations) == 0


# ---------------------------------------------------------------------------
# Manifest compliance
# ---------------------------------------------------------------------------


class TestManifest:
    def test_manifest_compliance(self, agent: RiskGateAgent) -> None:
        m = agent.manifest
        assert m.name == "risk_gate"
        assert m.llm_dependency is False
        assert m.pipeline_mode == "full"
        assert "risk" in m.tags
        assert "gate" in m.tags
        assert "safety" in m.tags
        assert "delta_budget" in m.tags
        assert "iv_crush" in m.tags


# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------


class TestExtensions:
    @pytest.mark.asyncio
    async def test_writes_summary_extension(self, agent: RiskGateAgent) -> None:
        rec = _make_rec(action="buy")
        state = _make_state()
        state.recommendations = [rec]
        result = await agent.run(state)
        assert "risk_gate" in result.extensions
        summary = result.extensions["risk_gate"]["summary"]
        assert summary["total_checked"] == 1
        assert summary["passed"] == 1
        assert summary["blocked"] == 0


# ---------------------------------------------------------------------------
# M2 v1.3 new tests — Delta Dollars budget
# ---------------------------------------------------------------------------


class TestDeltaBudget:
    @pytest.mark.asyncio
    async def test_blocks_when_budget_exceeded(self, agent: RiskGateAgent) -> None:
        """Should block low-score recs when delta budget exceeded."""
        agent._rules["delta_dollars_budget_pct"] = 0.30
        rec1 = _make_rec(action="buy", score=90, delta_dollars_delta=25000)
        rec2 = _make_rec(action="buy", score=70, delta_dollars_delta=10000)
        rec3 = _make_rec(action="buy", score=50, delta_dollars_delta=5000)
        state = _make_state(
            positions={"total_nav": 100000.0, "cash": 50000.0, "total_position_pct": 0.30, "holdings": []}
        )
        state.recommendations = [rec1, rec2, rec3]
        result = await agent.run(state)
        # Budget = 30000. rec1(25000) + rec2(10000) = 35000 > 30000
        # rec3(5000) would make it 40000
        # So rec1 passes, rec2 blocked, rec3 blocked
        assert len(result.recommendations) >= 1
        assert result.recommendations[0].score == 90
        assert len(result.blocked_recommendations) >= 1

    @pytest.mark.asyncio
    async def test_allows_when_budget_sufficient(self, agent: RiskGateAgent) -> None:
        """Should allow all recs when within budget."""
        agent._rules["delta_dollars_budget_pct"] = 0.30
        rec1 = _make_rec(action="buy", score=90, delta_dollars_delta=10000)
        rec2 = _make_rec(action="buy", score=80, delta_dollars_delta=10000)
        state = _make_state(
            positions={"total_nav": 100000.0, "cash": 50000.0, "total_position_pct": 0.30, "holdings": []}
        )
        state.recommendations = [rec1, rec2]
        result = await agent.run(state)
        # Budget = 30000, total delta = 20000 → both pass
        assert len(result.recommendations) == 2
        assert len(result.blocked_recommendations) == 0

    @pytest.mark.asyncio
    async def test_block_reason_contains_budget_info(self, agent: RiskGateAgent) -> None:
        """Block reason should include budget usage details."""
        agent._rules["delta_dollars_budget_pct"] = 0.30
        rec1 = _make_rec(action="buy", score=90, delta_dollars_delta=35000)
        state = _make_state(
            positions={"total_nav": 100000.0, "cash": 50000.0, "total_position_pct": 0.30, "holdings": []}
        )
        state.recommendations = [rec1]
        result = await agent.run(state)
        # 35000 > 30000 → blocked
        assert len(result.blocked_recommendations) == 1
        assert "Delta budget exceeded" in result.blocked_recommendations[0].block_reason


# ---------------------------------------------------------------------------
# M2 v1.3 new tests — IV crush guard
# ---------------------------------------------------------------------------


class TestIVCrushGuard:
    @pytest.mark.asyncio
    async def test_blocks_when_iv_crush_high(self, agent: RiskGateAgent) -> None:
        """Should block buy when IV crush risk is high."""
        agent._rules["iv_crush_block_threshold"] = "high"
        rec = _make_rec(action="buy", ticker="QQQ")
        state = _make_state(
            options_step1={
                "QQQ": {
                    "iv_crush_risk": {
                        "level": "high",
                        "upcoming_event": "QQQ Earnings",
                        "days_until_event": 3,
                    }
                }
            }
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 0
        assert len(result.blocked_recommendations) == 1
        assert "IV crush risk" in result.blocked_recommendations[0].block_reason

    @pytest.mark.asyncio
    async def test_allows_when_iv_crush_medium(self, agent: RiskGateAgent) -> None:
        """Should allow when IV crush risk is medium (below threshold)."""
        agent._rules["iv_crush_block_threshold"] = "high"
        rec = _make_rec(action="buy", ticker="QQQ")
        state = _make_state(
            options_step1={
                "QQQ": {
                    "iv_crush_risk": {
                        "level": "medium",
                        "upcoming_event": "FOMC",
                        "days_until_event": 4,
                    }
                }
            }
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1

    @pytest.mark.asyncio
    async def test_skips_for_hold_action(self, agent: RiskGateAgent) -> None:
        """IV crush guard should not apply to hold actions."""
        agent._rules["iv_crush_block_threshold"] = "high"
        rec = _make_rec(action="hold", ticker="QQQ")
        state = _make_state(
            options_step1={
                "QQQ": {
                    "iv_crush_risk": {
                        "level": "high",
                        "upcoming_event": "QQQ Earnings",
                        "days_until_event": 3,
                    }
                }
            }
        )
        state.recommendations = [rec]
        result = await agent.run(state)
        assert len(result.recommendations) == 1
