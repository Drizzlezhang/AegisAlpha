"""Tests for PipelineState v1.4 — M3 new fields."""

from aegis.pipeline.state import PipelineState


def test_v14_new_fields_exist():
    """All 5 v1.4 fields should exist with correct default types."""
    state = PipelineState()

    assert isinstance(state.thesis_cards, dict)
    assert isinstance(state.kol_signals, dict)
    assert isinstance(state.universe_candidates, list)
    assert isinstance(state.weight_snapshot, dict)
    assert isinstance(state.thesis_validation_results, dict)


def test_v14_new_fields_default_empty():
    """All v1.4 fields should default to empty."""
    state = PipelineState()

    assert state.thesis_cards == {}
    assert state.kol_signals == {}
    assert state.universe_candidates == []
    assert state.weight_snapshot == {}
    assert state.thesis_validation_results == {}


def test_v14_backward_compatible_with_v13():
    """v1.3 fields should still work in v1.4."""
    state = PipelineState(tickers=["QQQ"], pipeline_mode="full")

    assert state.tickers == ["QQQ"]
    assert state.pipeline_mode == "full"
    assert state.smart_money_data == {}
    assert state.fund_flow_data == {}
    assert state.trigger_conditions == []
    assert state.broker_positions == {}
    assert state.strategy_comparisons == {}
    assert state.scenario_pnl == {}


def test_v14_new_fields_writable():
    """New v1.4 fields should accept data."""
    state = PipelineState(
        thesis_cards={"QQQ": {"direction": "long", "entry_mode": "active_left"}},
        kol_signals={"QQQ": {"source": "stocktwits", "direction": "bullish"}},
        universe_candidates=[{"ticker": "AAPL", "signal": "breakout"}],
        weight_snapshot={"trend_phase": {"weight": 1.2}, "smart_money": {"weight": 0.8}},
        thesis_validation_results={"QQQ": {"status": "valid"}},
    )

    assert state.thesis_cards["QQQ"]["direction"] == "long"
    assert state.kol_signals["QQQ"]["source"] == "stocktwits"
    assert len(state.universe_candidates) == 1
    assert state.weight_snapshot["trend_phase"]["weight"] == 1.2
    assert state.thesis_validation_results["QQQ"]["status"] == "valid"


def test_v14_v13_fields_unaffected():
    """v1.3 fields should not be affected by v1.4 additions."""
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
