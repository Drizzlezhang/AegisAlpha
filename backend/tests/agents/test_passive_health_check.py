"""Test PassiveHealthCheckAgent — stop loss, DTE, theta, deviation, health scores."""

from __future__ import annotations

from typing import Any

import pytest

from aegis.agents.passive_health_check_agent import PassiveHealthCheckAgent
from aegis.pipeline.state import PipelineState


def _make_state(**overrides: Any) -> PipelineState:
    defaults: dict[str, Any] = {
        "tickers": ["QQQ"],
        "tickers_holdings_passive": ["QQQ"],
        "positions": {
            "total_nav": 100000.0,
            "cash": 50000.0,
            "holdings": [
                {
                    "ticker": "QQQ",
                    "shares": 100,
                    "avg_cost": 400.0,
                    "dte": 365,
                    "theta": -0.02,
                    "stop_loss": {
                        "mode": "support_based",
                        "trigger_price": 380.0,
                        "support_level": 380.0,
                    },
                }
            ],
        },
        "market_data": {
            "QQQ": {"price": 420.0},
        },
        "entry_mode": {"QQQ": "passive"},
    }
    defaults.update(overrides)
    return PipelineState(**defaults)


@pytest.fixture
def agent(mock_memory: Any, mock_tools: Any, mock_config: Any) -> PassiveHealthCheckAgent:
    return PassiveHealthCheckAgent(memory=mock_memory, tools=mock_tools, config=mock_config)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


class TestManifest:
    def test_manifest_compliance(self, mock_memory: Any, mock_tools: Any, mock_config: Any) -> None:
        agent = PassiveHealthCheckAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        m = agent.manifest
        assert m.name == "passive_health_check"
        assert m.llm_dependency is False
        assert m.pipeline_mode == "lightweight"
        assert "passive" in m.tags
        assert "health" in m.tags
        assert "rule_only" in m.tags


# ---------------------------------------------------------------------------
# Dynamic stop loss — support_based
# ---------------------------------------------------------------------------


class TestStopLossSupportBased:
    @pytest.mark.asyncio
    async def test_alerts_when_price_below_support(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            market_data={"QQQ": {"price": 370.0}},
        )
        result = await agent.run(state)
        alerts = result.passive_health_alerts
        assert len(alerts) >= 1
        stop_alerts = [a for a in alerts if a["type"] == "stop_loss_breach"]
        assert len(stop_alerts) == 1
        assert stop_alerts[0]["mode"] == "support_based"
        assert stop_alerts[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_no_alert_when_price_above_support(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            market_data={"QQQ": {"price": 420.0}},
        )
        result = await agent.run(state)
        stop_alerts = [a for a in result.passive_health_alerts if a["type"] == "stop_loss_breach"]
        assert len(stop_alerts) == 0

    @pytest.mark.asyncio
    async def test_no_alert_when_no_stop_loss_config(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {"ticker": "QQQ", "shares": 100, "avg_cost": 400.0}
                ],
            },
            market_data={"QQQ": {"price": 370.0}},
        )
        result = await agent.run(state)
        stop_alerts = [a for a in result.passive_health_alerts if a["type"] == "stop_loss_breach"]
        assert len(stop_alerts) == 0


# ---------------------------------------------------------------------------
# Dynamic stop loss — fixed_pct
# ---------------------------------------------------------------------------


class TestStopLossFixedPct:
    @pytest.mark.asyncio
    async def test_alerts_when_drop_exceeds_threshold(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {
                        "ticker": "QQQ",
                        "shares": 100,
                        "avg_cost": 400.0,
                        "stop_loss": {
                            "mode": "fixed_pct",
                            "trigger_price": 360.0,
                            "drop_pct_from_entry": 0.08,
                        },
                    }
                ],
            },
            market_data={"QQQ": {"price": 360.0}},  # 10% drop > 8%
        )
        result = await agent.run(state)
        stop_alerts = [a for a in result.passive_health_alerts if a["type"] == "stop_loss_breach"]
        assert len(stop_alerts) == 1
        assert stop_alerts[0]["mode"] == "fixed_pct"

    @pytest.mark.asyncio
    async def test_no_alert_when_drop_within_threshold(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {
                        "ticker": "QQQ",
                        "shares": 100,
                        "avg_cost": 400.0,
                        "stop_loss": {
                            "mode": "fixed_pct",
                            "trigger_price": 360.0,
                            "drop_pct_from_entry": 0.08,
                        },
                    }
                ],
            },
            market_data={"QQQ": {"price": 380.0}},  # 5% drop < 8%
        )
        result = await agent.run(state)
        stop_alerts = [a for a in result.passive_health_alerts if a["type"] == "stop_loss_breach"]
        assert len(stop_alerts) == 0


# ---------------------------------------------------------------------------
# DTE warning
# ---------------------------------------------------------------------------


class TestDTEWarning:
    @pytest.mark.asyncio
    async def test_alerts_when_dte_below_90(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {"ticker": "QQQ", "shares": 100, "avg_cost": 400.0, "dte": 60}
                ],
            },
        )
        result = await agent.run(state)
        dte_alerts = [a for a in result.passive_health_alerts if a["type"] == "leaps_dte_warning"]
        assert len(dte_alerts) == 1
        assert dte_alerts[0]["dte"] == 60

    @pytest.mark.asyncio
    async def test_no_alert_when_dte_above_90(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {"ticker": "QQQ", "shares": 100, "avg_cost": 400.0, "dte": 365}
                ],
            },
        )
        result = await agent.run(state)
        dte_alerts = [a for a in result.passive_health_alerts if a["type"] == "leaps_dte_warning"]
        assert len(dte_alerts) == 0

    @pytest.mark.asyncio
    async def test_no_alert_when_no_dte_field(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {"ticker": "QQQ", "shares": 100, "avg_cost": 400.0}
                ],
            },
        )
        result = await agent.run(state)
        dte_alerts = [a for a in result.passive_health_alerts if a["type"] == "leaps_dte_warning"]
        assert len(dte_alerts) == 0


# ---------------------------------------------------------------------------
# Theta acceleration
# ---------------------------------------------------------------------------


class TestThetaAcceleration:
    @pytest.mark.asyncio
    async def test_alerts_via_5d_avg_multiplier(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {
                        "ticker": "QQQ",
                        "shares": 100,
                        "avg_cost": 400.0,
                        "dte": 30,
                        "theta": -0.08,
                        "theta_5d_avg": 0.04,
                    }
                ],
            },
        )
        result = await agent.run(state)
        theta_alerts = [a for a in result.passive_health_alerts if a["type"] == "theta_accelerating"]
        assert len(theta_alerts) == 1

    @pytest.mark.asyncio
    async def test_alerts_via_daily_decay_pct(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {
                        "ticker": "QQQ",
                        "shares": 100,
                        "avg_cost": 400.0,
                        "dte": 30,
                        "theta": -0.05,
                        "option_value": 1.50,
                    }
                ],
            },
        )
        result = await agent.run(state)
        theta_alerts = [a for a in result.passive_health_alerts if a["type"] == "theta_accelerating"]
        # 0.05 / 1.50 = 3.3% > 2%
        assert len(theta_alerts) == 1

    @pytest.mark.asyncio
    async def test_no_alert_when_dte_above_60(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {
                        "ticker": "QQQ",
                        "shares": 100,
                        "avg_cost": 400.0,
                        "dte": 90,
                        "theta": -0.08,
                        "theta_5d_avg": 0.04,
                    }
                ],
            },
        )
        result = await agent.run(state)
        theta_alerts = [a for a in result.passive_health_alerts if a["type"] == "theta_accelerating"]
        assert len(theta_alerts) == 0

    @pytest.mark.asyncio
    async def test_no_alert_when_no_theta(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {"ticker": "QQQ", "shares": 100, "avg_cost": 400.0, "dte": 30}
                ],
            },
        )
        result = await agent.run(state)
        theta_alerts = [a for a in result.passive_health_alerts if a["type"] == "theta_accelerating"]
        assert len(theta_alerts) == 0


# ---------------------------------------------------------------------------
# Price deviation
# ---------------------------------------------------------------------------


class TestPriceDeviation:
    @pytest.mark.asyncio
    async def test_alerts_when_deviation_exceeds_10pct(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {"ticker": "QQQ", "shares": 100, "avg_cost": 400.0}
                ],
            },
            market_data={"QQQ": {"price": 450.0}},  # +12.5%
        )
        result = await agent.run(state)
        dev_alerts = [a for a in result.passive_health_alerts if a["type"] == "price_deviation"]
        assert len(dev_alerts) == 1
        assert dev_alerts[0]["deviation_pct"] > 0.10

    @pytest.mark.asyncio
    async def test_no_alert_when_deviation_within_10pct(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {"ticker": "QQQ", "shares": 100, "avg_cost": 400.0}
                ],
            },
            market_data={"QQQ": {"price": 420.0}},  # +5%
        )
        result = await agent.run(state)
        dev_alerts = [a for a in result.passive_health_alerts if a["type"] == "price_deviation"]
        assert len(dev_alerts) == 0

    @pytest.mark.asyncio
    async def test_no_alert_when_no_price_data(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {"ticker": "QQQ", "shares": 100, "avg_cost": 400.0}
                ],
            },
            market_data={},
        )
        result = await agent.run(state)
        dev_alerts = [a for a in result.passive_health_alerts if a["type"] == "price_deviation"]
        assert len(dev_alerts) == 0


# ---------------------------------------------------------------------------
# Health scores
# ---------------------------------------------------------------------------


class TestHealthScores:
    @pytest.mark.asyncio
    async def test_healthy_holding_scores_100(self, agent: PassiveHealthCheckAgent) -> None:
        """A holding with no issues should score 100."""
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {"ticker": "QQQ", "shares": 100, "avg_cost": 400.0, "dte": 365}
                ],
            },
            market_data={"QQQ": {"price": 420.0}},
        )
        result = await agent.run(state)
        assert result.health_scores["QQQ"] == 100.0
        assert len(result.passive_health_alerts) == 0

    @pytest.mark.asyncio
    async def test_multiple_issues_reduce_score(self, agent: PassiveHealthCheckAgent) -> None:
        """Stop loss breach + DTE warning should reduce score."""
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {
                        "ticker": "QQQ",
                        "shares": 100,
                        "avg_cost": 400.0,
                        "dte": 60,
                        "stop_loss": {
                            "mode": "support_based",
                            "trigger_price": 380.0,
                            "support_level": 380.0,
                        },
                    }
                ],
            },
            market_data={"QQQ": {"price": 370.0}},
        )
        result = await agent.run(state)
        # stop_loss: -30, dte: -20 = 50
        assert result.health_scores["QQQ"] == 50.0

    @pytest.mark.asyncio
    async def test_score_never_below_zero(self, agent: PassiveHealthCheckAgent) -> None:
        """Health score should be clamped at 0."""
        state = _make_state(
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {
                        "ticker": "QQQ",
                        "shares": 100,
                        "avg_cost": 400.0,
                        "dte": 30,
                        "theta": -0.08,
                        "theta_5d_avg": 0.04,
                        "stop_loss": {
                            "mode": "support_based",
                            "trigger_price": 380.0,
                            "support_level": 380.0,
                        },
                    }
                ],
            },
            market_data={"QQQ": {"price": 370.0}},
        )
        result = await agent.run(state)
        # stop_loss: -30, dte: -20, theta: -25 = 25 (not below 0)
        assert result.health_scores["QQQ"] >= 0.0


# ---------------------------------------------------------------------------
# Multiple tickers
# ---------------------------------------------------------------------------


class TestMultipleTickers:
    @pytest.mark.asyncio
    async def test_checks_all_passive_tickers(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            tickers_holdings_passive=["QQQ", "SPY"],
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {"ticker": "QQQ", "shares": 100, "avg_cost": 400.0, "dte": 365},
                    {"ticker": "SPY", "shares": 50, "avg_cost": 500.0, "dte": 60},
                ],
            },
            market_data={
                "QQQ": {"price": 420.0},
                "SPY": {"price": 510.0},
            },
        )
        result = await agent.run(state)
        assert "QQQ" in result.health_scores
        assert "SPY" in result.health_scores
        assert result.health_scores["QQQ"] == 100.0
        assert result.health_scores["SPY"] < 100.0  # DTE warning

    @pytest.mark.asyncio
    async def test_skips_tickers_not_in_holdings(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(
            tickers_holdings_passive=["QQQ", "SPY"],
            positions={
                "total_nav": 100000.0,
                "cash": 50000.0,
                "holdings": [
                    {"ticker": "QQQ", "shares": 100, "avg_cost": 400.0, "dte": 365},
                ],
            },
            market_data={"QQQ": {"price": 420.0}},
        )
        result = await agent.run(state)
        assert "QQQ" in result.health_scores
        assert "SPY" not in result.health_scores


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_passive_tickers(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state(tickers_holdings_passive=[])
        result = await agent.run(state)
        assert result.passive_health_alerts == []
        assert result.health_scores == {}

    @pytest.mark.asyncio
    async def test_writes_extensions(self, agent: PassiveHealthCheckAgent) -> None:
        state = _make_state()
        result = await agent.run(state)
        assert "passive_health_check" in result.extensions
        ext = result.extensions["passive_health_check"]
        assert "summary" in ext
        assert ext["summary"]["tickers_checked"] == 1
