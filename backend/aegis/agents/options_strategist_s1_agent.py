"""Options Strategist Step 1 Agent — Option chain screening with Greeks + IV Crush.

Pure calculation, no LLM dependency. Writes to options_step1 and extensions.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
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

# IV Crush thresholds
IV_CRUSH_EVENT_DAYS = 5  # Days before event to flag IV crush risk
IV_CRUSH_RANK_HIGH = 0.70  # IV rank > 70% = high risk
IV_CRUSH_RANK_MEDIUM = 0.50  # IV rank > 50% = medium risk

# Known market-moving events (approximate schedule)
KNOWN_EVENTS: list[dict[str, Any]] = [
    {"name": "FOMC", "type": "fomc", "frequency_days": 42},
    {"name": "CPI", "type": "cpi", "frequency_days": 30},
    {"name": "NFP", "type": "nfp", "frequency_days": 30},
]


class OptionsStrategistS1Agent(BaseAgent):
    """Screen option chain and compute Greeks for candidate contracts.

    Input: state.market_data[ticker] OHLCV + VIX, option chain data
    Output: state.options_step1[ticker] — list of candidate contracts with Greeks
    """

    name = "options_strategist_s1"
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="options_strategist_s1",
        version="0.2.0",
        requires=["market_data"],
        provides=["options_step1", "extensions.options_strategist_s1"],
        tags=["options", "screening", "signal", "iv_crush"],
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
                with_greeks: list[dict[str, Any]] = []
                for c in chain:
                    try:
                        greeks = compute_greeks(
                            option_type=c.get("type", "call"),
                            S=c.get("spot_price", 0.0),
                            K=c.get("strike", 0.0),
                            T=c.get("dte", 365) / 365.0,
                            r=0.05,
                            sigma=c.get("iv", 0.2),
                        )
                        c["delta"] = greeks.delta
                        c["gamma"] = greeks.gamma
                        c["theta"] = greeks.theta
                        c["vega"] = greeks.vega
                        c["rho"] = greeks.rho
                    except Exception:
                        pass
                    with_greeks.append(c)

                # Apply screening filters
                filtered = self._apply_filters(with_greeks)

                # Compute IV data and IV crush risk
                iv_data = self._compute_iv(ticker, state.market_data, with_greeks)
                iv_crush_risk = self._assess_iv_crush(ticker, state.market_data, iv_data)

                state.options_step1[ticker] = {
                    "candidates": filtered,
                    "total_screened": len(chain),
                    "total_passed": len(filtered),
                    "iv_data": iv_data,
                    "iv_crush_risk": iv_crush_risk,
                }

                self.write_extension(
                    state,
                    "screening_raw",
                    {
                        "total": len(chain),
                        "passed": len(filtered),
                        "filters_applied": self._get_filter_config(),
                        "iv_percentile": iv_data.get("percentile"),
                        "iv_crush_risk": iv_crush_risk,
                    },
                )

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
    def _compute_iv(
        ticker: str,
        market_data: dict[str, Any],
        contracts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compute IV statistics from option chain data.

        Returns IV percentile, current IV, mean IV, and IV rank.
        """
        ivs = [c.get("iv", 0.0) for c in contracts if c.get("iv", 0.0) > 0]
        if not ivs:
            return {"percentile": 0.0, "current": 0.0, "mean": 0.0, "count": 0}

        current_iv = ivs[0]  # ATM IV as proxy
        mean_iv = statistics.mean(ivs)
        # IV percentile: fraction of contracts with IV <= current
        below = sum(1 for v in ivs if v <= current_iv)
        percentile = below / len(ivs)

        return {
            "percentile": round(percentile, 4),
            "current": round(current_iv, 4),
            "mean": round(mean_iv, 4),
            "min": round(min(ivs), 4),
            "max": round(max(ivs), 4),
            "count": len(ivs),
        }

    @staticmethod
    def _assess_iv_crush(
        ticker: str,
        market_data: dict[str, Any],
        iv_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Assess IV crush risk based on upcoming events and IV rank.

        Checks:
        - Upcoming events (earnings/FOMC/CPI/NFP) within IV_CRUSH_EVENT_DAYS
        - Current IV rank vs thresholds

        Returns:
        {
            "level": "high" | "medium" | "low",
            "reason": str,
            "upcoming_event": str | None,
            "days_until_event": int | None,
        }
        """
        iv_percentile = iv_data.get("percentile", 0.0)
        now = datetime.now(timezone.utc)

        # Check for upcoming events
        upcoming_event: dict[str, Any] | None = None
        days_until: int | None = None

        # Check ticker-specific earnings from market_data
        ticker_data = market_data.get(ticker, {})
        earnings_date = ticker_data.get("next_earnings_date", "")
        if earnings_date:
            try:
                edate = datetime.fromisoformat(earnings_date).replace(tzinfo=timezone.utc)
                delta = (edate - now).days
                if 0 <= delta <= IV_CRUSH_EVENT_DAYS:
                    upcoming_event = {"name": f"{ticker} Earnings", "type": "earnings"}
                    days_until = delta
            except (ValueError, TypeError):
                pass

        # Check macro events from market_data
        macro_events = market_data.get("macro_events", [])
        for event in macro_events:
            event_date = event.get("date", "")
            if not event_date:
                continue
            try:
                edate = datetime.fromisoformat(event_date).replace(tzinfo=timezone.utc)
                delta = (edate - now).days
                if 0 <= delta <= IV_CRUSH_EVENT_DAYS:
                    upcoming_event = {
                        "name": event.get("name", "Unknown Event"),
                        "type": event.get("type", "unknown"),
                    }
                    days_until = delta
                    break
            except (ValueError, TypeError):
                pass

        # Determine risk level
        if upcoming_event and iv_percentile > IV_CRUSH_RANK_HIGH:
            level = "high"
            reason = (
                f"IV rank {iv_percentile:.0%} > {IV_CRUSH_RANK_HIGH:.0%} "
                f"with {upcoming_event['name']} in {days_until}d. "
                "建议事件后再入场"
            )
        elif upcoming_event and iv_percentile > IV_CRUSH_RANK_MEDIUM:
            level = "medium"
            reason = (
                f"IV rank {iv_percentile:.0%} elevated with {upcoming_event['name']} in {days_until}d"
            )
        elif iv_percentile > IV_CRUSH_RANK_HIGH:
            level = "medium"
            reason = f"IV rank {iv_percentile:.0%} > {IV_CRUSH_RANK_HIGH:.0%} (no imminent event)"
        else:
            level = "low"
            reason = f"IV rank {iv_percentile:.0%}, no imminent event risk"

        return {
            "level": level,
            "reason": reason,
            "upcoming_event": upcoming_event["name"] if upcoming_event else None,
            "days_until_event": days_until,
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
