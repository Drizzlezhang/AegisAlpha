"""Test PipelineState v1.2 contract — all fields must exist with correct types."""

from datetime import datetime

from aegis.pipeline.state import (
    BlockedRecommendation,
    FactorScore,
    OptionContract,
    PipelineState,
    Recommendation,
)


class TestPipelineStateV12:
    """Verify PipelineState v1.2 schema completeness."""

    def test_state_instantiation_defaults(self) -> None:
        """PipelineState should instantiate with all defaults."""
        state = PipelineState()
        assert state.pipeline_id == ""
        assert state.mode == "manual"
        assert isinstance(state.triggered_at, datetime)
        assert state.tickers == []

    def test_v12_dual_pipeline_fields(self) -> None:
        """v1.2: pipeline_mode, tickers_holdings, entry_mode fields exist."""
        state = PipelineState()
        assert state.pipeline_mode == "full"
        assert state.tickers_holdings_active == []
        assert state.tickers_holdings_passive == []
        assert state.entry_mode == {}

    def test_v12_extensions_field(self) -> None:
        """v1.2: extensions dict exists and is writable."""
        state = PipelineState()
        state.extensions["test_agent"] = {"key": "value"}
        assert state.extensions["test_agent"]["key"] == "value"

    def test_v12_pending_triggers_field(self) -> None:
        """v1.2: pending_triggers list exists."""
        state = PipelineState()
        assert state.pending_triggers == []

    def test_v12_lightweight_fields(self) -> None:
        """v1.2: passive_health_alerts, health_scores, delta_dollars_delta exist."""
        state = PipelineState()
        assert state.passive_health_alerts == []
        assert state.health_scores == {}
        assert state.delta_dollars_delta == 0.0

    def test_v12_entry_mode_dict(self) -> None:
        """v1.2: entry_mode accepts valid Literal values."""
        state = PipelineState(
            entry_mode={
                "QQQ": "passive",
                "AAPL": "active_left",
                "MSFT": "active_right",
                "SPY": "cc",
            }
        )
        assert state.entry_mode["QQQ"] == "passive"
        assert state.entry_mode["AAPL"] == "active_left"
        assert state.entry_mode["MSFT"] == "active_right"
        assert state.entry_mode["SPY"] == "cc"

    def test_recommendation_model(self) -> None:
        """Recommendation model should have all fields."""
        rec = Recommendation(
            ticker="QQQ",
            action="buy",
            strategy="leaps_call",
            rationale="test",
        )
        assert rec.ticker == "QQQ"
        assert rec.action == "buy"
        assert rec.strategy == "leaps_call"
        assert rec.factor_scores == []
        assert rec.option_contracts == []
        assert rec.urgency == "medium"
        assert rec.score == 0.0
        assert rec.delta_dollars_delta == 0.0

    def test_blocked_recommendation_model(self) -> None:
        """BlockedRecommendation should wrap a Recommendation with block reason."""
        rec = Recommendation(
            ticker="QQQ",
            action="buy",
            strategy="leaps_call",
            rationale="test",
        )
        blocked = BlockedRecommendation(
            recommendation=rec,
            block_reason="VIX > 30",
        )
        assert blocked.block_reason == "VIX > 30"
        assert blocked.recommendation.ticker == "QQQ"

    def test_factor_score_model(self) -> None:
        """FactorScore model should have factor, score, confidence, rationale."""
        fs = FactorScore(factor="trend", score=75.0, confidence=0.8, rationale="uptrend")
        assert fs.factor == "trend"
        assert fs.score == 75.0
        assert fs.confidence == 0.8
        assert fs.rationale == "uptrend"

    def test_option_contract_model(self) -> None:
        """OptionContract model should have all greeks fields."""
        oc = OptionContract(
            symbol="QQQ",
            type="call",
            strike=500.0,
            expiration="2025-06-20",
            dte=365,
            bid=10.0,
            ask=10.5,
            delta=0.6,
            gamma=0.02,
            theta=-0.05,
            vega=0.15,
            iv=0.25,
        )
        assert oc.symbol == "QQQ"
        assert oc.type == "call"
        assert oc.delta == 0.6
        assert oc.dte == 365

    def test_scratchpad_and_error_flags(self) -> None:
        """Scratchpad and error_flags should be writable."""
        state = PipelineState()
        state.scratchpad["echo"] = "test trace"
        state.error_flags.append({"agent": "test", "error": "mock error"})
        assert state.scratchpad["echo"] == "test trace"
        assert len(state.error_flags) == 1

    def test_agent_timings(self) -> None:
        """agent_timings dict should be writable."""
        state = PipelineState()
        state.agent_timings["data_harvester"] = 1.5
        assert state.agent_timings["data_harvester"] == 1.5
