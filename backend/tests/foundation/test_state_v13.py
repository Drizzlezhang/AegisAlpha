"""Tests for PipelineState v1.3 — M2 new fields."""

from aegis.pipeline.state import PipelineState


def test_v13_new_fields_exist():
    """All 6 v1.3 fields should exist with correct default types."""
    state = PipelineState()

    assert isinstance(state.smart_money_data, dict)
    assert isinstance(state.fund_flow_data, dict)
    assert isinstance(state.trigger_conditions, list)
    assert isinstance(state.broker_positions, dict)
    assert isinstance(state.strategy_comparisons, dict)
    assert isinstance(state.scenario_pnl, dict)


def test_v13_new_fields_default_empty():
    """All v1.3 fields should default to empty."""
    state = PipelineState()

    assert state.smart_money_data == {}
    assert state.fund_flow_data == {}
    assert state.trigger_conditions == []
    assert state.broker_positions == {}
    assert state.strategy_comparisons == {}
    assert state.scenario_pnl == {}


def test_v13_backward_compatible():
    """Existing v1.2 fields should still work."""
    state = PipelineState(tickers=["QQQ"], pipeline_mode="full")

    assert state.tickers == ["QQQ"]
    assert state.pipeline_mode == "full"
    assert state.market_data == {}
    assert state.recommendations == []
    assert state.health_scores == {}


def test_v13_new_fields_writable():
    """New fields should accept data."""
    state = PipelineState(
        smart_money_data={"QQQ": {"score": 75}},
        fund_flow_data={"SPY": {"net_flow": 1.2e9}},
        trigger_conditions=[{"ticker": "QQQ", "condition": "price > 500"}],
        broker_positions={"futu": [{"ticker": "QQQ", "qty": 100}]},
        strategy_comparisons={"QQQ": [{"strategy": "leaps_call", "pnl": 500}]},
        scenario_pnl={"bull": {"total": 10000}},
    )

    assert state.smart_money_data["QQQ"]["score"] == 75
    assert state.fund_flow_data["SPY"]["net_flow"] == 1.2e9
    assert len(state.trigger_conditions) == 1
    assert state.broker_positions["futu"][0]["ticker"] == "QQQ"
    assert state.strategy_comparisons["QQQ"][0]["pnl"] == 500
    assert state.scenario_pnl["bull"]["total"] == 10000
