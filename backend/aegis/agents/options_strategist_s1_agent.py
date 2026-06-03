"""Options Strategist Step 1 Agent — Option chain screening with Greeks.

Pure calculation, no LLM dependency. Writes to options_step1 and extensions.
"""
from __future__ import annotations

from typing import Any, ClassVar

from aegis.agents.base import BaseAgent
from aegis.calculators.greeks import compute_greeks
from aegis.pipeline.state import PipelineState
from aegis.registry.agent_registry import AgentManifest

# Default screening thresholds
DEFAULT_MIN_DTE = 365
DEFAULT_MAX_DTE = 730
DEFAULT_DELTA_MIN = 0.50
DEFAULT_DELTA_MAX = 0.85
DEFAULT_MIN_OI = 100
DEFAULT_MAX_SPREAD_PCT = 0.05


class OptionsStrategistS1Agent(BaseAgent):
    """Screen option chain and compute Greeks for candidate contracts.

    Input: state.market_data[ticker] OHLCV + VIX, option chain data
    Output: state.options_step1[ticker] — list of candidate contracts with Greeks
    """

    name = "options_strategist_s1"
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="options_strategist_s1",
        version="0.1.0",
        requires=["market_data"],
        provides=["options_step1", "extensions.options_strategist_s1"],
        tags=["options", "screening", "signal"],
        llm_dependency=False,
        parallel_group="signal_analysts",
        pipeline_mode="full",
    )

    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            try:
                chain = state.market_data.get(ticker, {}).get("option_chain", [])
                if not chain or not isinstance(chain, list):
                    state.options_step1[ticker] = {}
                    continue

                # Compute Greeks for all contracts
                with_greeks = compute_greeks(chain)

                # Apply screening filters
                filtered = self._apply_filters(with_greeks)

                state.options_step1[ticker] = {
                    "candidates": filtered,
                    "total_screened": len(chain),
                    "total_passed": len(filtered),
                }

                self.write_extension(state, "screening_raw", {
                    "total": len(chain),
                    "passed": len(filtered),
                    "filters_applied": self._get_filter_config(),
                })

            except Exception as e:
                self._flag_error(state, ticker, str(e))

        return state

    def _apply_filters(self, contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply screening filters to option contracts."""
        passed: list[dict[str, Any]] = []
        for c in contracts:
            dte = c.get("dte", 0)
            if dte < DEFAULT_MIN_DTE or dte > DEFAULT_MAX_DTE:
                continue

            delta = abs(c.get("delta", 0.0))
            if delta < DEFAULT_DELTA_MIN or delta > DEFAULT_DELTA_MAX:
                continue

            oi = c.get("oi", 0)
            if oi < DEFAULT_MIN_OI:
                continue

            bid = c.get("bid", 0.0)
            ask = c.get("ask", 0.0)
            mid = (bid + ask) / 2.0
            if mid > 0:
                spread_pct = (ask - bid) / mid
                if spread_pct > DEFAULT_MAX_SPREAD_PCT:
                    continue

            passed.append(c)

        return passed

    @staticmethod
    def _get_filter_config() -> dict[str, Any]:
        return {
            "min_dte": DEFAULT_MIN_DTE,
            "max_dte": DEFAULT_MAX_DTE,
            "delta_min": DEFAULT_DELTA_MIN,
            "delta_max": DEFAULT_DELTA_MAX,
            "min_oi": DEFAULT_MIN_OI,
            "max_spread_pct": DEFAULT_MAX_SPREAD_PCT,
        }

    @staticmethod
    def _flag_error(state: PipelineState, ticker: str, message: str) -> None:
        state.error_flags.append(
            {
                "agent": "options_strategist_s1",
                "ticker": ticker,
                "error": message,
            }
        )
