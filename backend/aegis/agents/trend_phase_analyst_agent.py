"""Trend/Phase Analyst Agent — Wyckoff phase detection + trend scoring.

Pure calculation, no LLM dependency. Writes to analyst_outputs and extensions.
"""
from __future__ import annotations

from typing import Any, ClassVar

from aegis.agents.base import BaseAgent
from aegis.calculators.trend import compute_trend_score, detect_wyckoff_phase
from aegis.pipeline.state import PipelineState
from aegis.registry.agent_registry import AgentManifest


class TrendPhaseAnalystAgent(BaseAgent):
    """Analyze trend direction and Wyckoff phase for each ticker.

    Input: state.market_data[ticker] OHLCV
    Output: state.analyst_outputs[ticker]["trend_phase"]
    """

    name = "trend_phase_analyst"
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="trend_phase_analyst",
        version="0.1.0",
        requires=["market_data"],
        provides=["analyst_outputs.trend_phase", "extensions.trend_phase_analyst"],
        tags=["trend", "phase", "signal"],
        llm_dependency=False,
        parallel_group="signal_analysts",
        pipeline_mode="both",
    )

    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            try:
                ohlcv = state.market_data.get(ticker, {})
                if not self._validate_ohlcv(ohlcv):
                    self._flag_error(state, ticker, "insufficient_ohlcv_data")
                    continue

                wyckoff = detect_wyckoff_phase(ohlcv)
                trend = compute_trend_score(ohlcv)

                state.analyst_outputs.setdefault(ticker, {})["trend_phase"] = {
                    "wyckoff_phase": wyckoff["phase"],
                    "trend_direction": trend["trend_direction"],
                    "trend_score": trend["trend_score"],
                    "confidence": round(
                        min(wyckoff["confidence"], trend["confidence"]), 2
                    ),
                }

                self.write_extension(state, "wyckoff_raw", wyckoff)
                self.write_extension(state, "trend_raw", trend)

            except Exception as e:
                self._flag_error(state, ticker, str(e))

        return state

    @staticmethod
    def _validate_ohlcv(ohlcv: dict[str, Any]) -> bool:
        """Check that OHLCV data has required fields with sufficient length."""
        required = ["open", "high", "low", "close"]
        for field in required:
            values = ohlcv.get(field, [])
            if not isinstance(values, list) or len(values) < 2:
                return False
        return True

    @staticmethod
    def _flag_error(state: PipelineState, ticker: str, message: str) -> None:
        state.error_flags.append(
            {
                "agent": "trend_phase_analyst",
                "ticker": ticker,
                "error": message,
            }
        )
