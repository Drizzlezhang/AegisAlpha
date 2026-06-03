"""Level Analyst Agent — Support/resistance levels + volume profile + GEX analysis.

Pure calculation, no LLM dependency. Writes to analyst_outputs and extensions.
"""
from __future__ import annotations

from typing import Any, ClassVar

from aegis.agents.base import BaseAgent
from aegis.calculators.gex import analyze_gex
from aegis.calculators.levels import compute_volume_profile, find_support_resistance
from aegis.pipeline.state import PipelineState
from aegis.registry.agent_registry import AgentManifest


class LevelAnalystAgent(BaseAgent):
    """Identify key price levels for each ticker.

    Input: state.market_data[ticker] OHLCV, optional GEX data
    Output: state.analyst_outputs[ticker]["levels"]
    """

    name = "level_analyst"
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="level_analyst",
        version="0.1.0",
        requires=["market_data"],
        provides=["analyst_outputs.levels", "extensions.level_analyst"],
        tags=["levels", "support", "resistance", "signal"],
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

                sr_levels = find_support_resistance(ohlcv)
                vol_profile = compute_volume_profile(ohlcv)

                # GEX integration (optional)
                gex_result: dict[str, Any] = {}
                gex_data = state.market_data.get(ticker, {}).get("gex")
                if gex_data and isinstance(gex_data, dict):
                    try:
                        gex_result = analyze_gex(gex_data)
                    except Exception:
                        gex_result = {
                            "gamma_flip_level": None,
                            "key_strikes": [],
                            "net_gex_signal": "neutral",
                        }

                state.analyst_outputs.setdefault(ticker, {})["levels"] = {
                    "support_levels": sr_levels["support_levels"],
                    "resistance_levels": sr_levels["resistance_levels"],
                    "key_levels": sr_levels["key_levels"],
                    "volume_nodes": vol_profile.get("volume_nodes", []),
                    "poc": vol_profile.get("poc"),
                    "value_area_high": vol_profile.get("value_area_high"),
                    "value_area_low": vol_profile.get("value_area_low"),
                    "gamma_flip_level": gex_result.get("gamma_flip_level"),
                    "gex_signal": gex_result.get("net_gex_signal", "neutral"),
                }

                self.write_extension(state, "sr_raw", sr_levels)
                self.write_extension(state, "volume_profile_raw", vol_profile)
                if gex_result:
                    self.write_extension(state, "gex_raw", gex_result)

            except Exception as e:
                self._flag_error(state, ticker, str(e))

        return state

    @staticmethod
    def _validate_ohlcv(ohlcv: dict[str, Any]) -> bool:
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
                "agent": "level_analyst",
                "ticker": ticker,
                "error": message,
            }
        )
