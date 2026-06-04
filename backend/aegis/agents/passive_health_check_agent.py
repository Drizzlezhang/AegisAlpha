"""Passive Health Check Agent — Lightweight pipeline health monitoring.

Input: state.tickers_holdings_passive, state.positions, state.market_data, state.entry_mode
Output: state.passive_health_alerts, state.health_scores
"""

from __future__ import annotations

from typing import Any, ClassVar

from aegis.agents.base import BaseAgent
from aegis.pipeline.state import PipelineState
from aegis.registry.agent_registry import AgentManifest

# Thresholds
DTE_WARNING_DAYS = 90
THETA_ACCEL_DTE_MAX = 60
THETA_ACCEL_MULTIPLIER = 1.5
THETA_DAILY_PCT_MAX = 0.02
PRICE_DEVIATION_THRESHOLD = 0.10


class PassiveHealthCheckAgent(BaseAgent):
    """Rule-only agent for passive holding health checks.

    No LLM dependency. Runs in Lightweight Pipeline only.
    Checks: dynamic stop loss, DTE warning, theta acceleration, price deviation.
    """

    name = "passive_health_check"
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="passive_health_check",
        version="0.1.0",
        requires=["tickers_holdings_passive", "positions", "market_data", "entry_mode"],
        provides=["passive_health_alerts", "health_scores", "extensions.passive_health_check"],
        tags=["passive", "health", "rule_only"],
        llm_dependency=False,
        parallel_group=None,
        pipeline_mode="lightweight",
        enabled=True,
    )

    async def run(self, state: PipelineState) -> PipelineState:
        alerts: list[dict[str, Any]] = []
        health_scores: dict[str, float] = {}

        for ticker in state.tickers_holdings_passive:
            pos = self._get_position(state, ticker)
            if not pos:
                continue

            ticker_alerts: list[dict[str, Any]] = []
            deductions = 0.0

            # 1. Dynamic stop loss check
            stop_alert = self._check_dynamic_stop(state, ticker, pos)
            if stop_alert:
                ticker_alerts.append(stop_alert)
                deductions += 30.0

            # 2. DTE warning (LEAPS DTE ≤ 90 days)
            dte_alert = self._check_dte(pos)
            if dte_alert:
                ticker_alerts.append(dte_alert)
                deductions += 20.0

            # 3. Theta acceleration detection
            theta_alert = self._check_theta_acceleration(pos)
            if theta_alert:
                ticker_alerts.append(theta_alert)
                deductions += 25.0

            # 4. Price deviation check
            dev_alert = self._check_price_deviation(state, ticker, pos)
            if dev_alert:
                ticker_alerts.append(dev_alert)
                deductions += 15.0

            alerts.extend(ticker_alerts)
            health_scores[ticker] = max(0.0, 100.0 - deductions)

        state.passive_health_alerts = alerts
        state.health_scores = health_scores

        self.write_extension(
            state,
            "summary",
            {
                "total_alerts": len(alerts),
                "tickers_checked": len(state.tickers_holdings_passive),
                "health_scores": health_scores,
            },
        )

        return state

    # ------------------------------------------------------------------
    # Position helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_position(state: PipelineState, ticker: str) -> dict[str, Any] | None:
        """Find a holding by ticker in state.positions."""
        holdings: list[dict[str, Any]] = state.positions.get("holdings", [])
        for h in holdings:
            if h.get("ticker") == ticker:
                return h
        return None

    @staticmethod
    def _get_current_price(state: PipelineState, ticker: str) -> float | None:
        """Get current price from market_data."""
        market = state.market_data.get(ticker, {})
        price = market.get("price")
        if price is not None:
            return float(price)
        return None

    # ------------------------------------------------------------------
    # Check 1: Dynamic stop loss
    # ------------------------------------------------------------------

    def _check_dynamic_stop(
        self, state: PipelineState, ticker: str, pos: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Check if stop loss has been triggered.

        support_based: price < support_level → alert
        fixed_pct: price drop > threshold → alert
        """
        stop_loss: dict[str, Any] = pos.get("stop_loss", {})
        if not stop_loss:
            return None

        current_price = self._get_current_price(state, ticker)
        if current_price is None:
            return None

        mode = stop_loss.get("mode", "")
        trigger_price = float(stop_loss.get("trigger_price", 0))

        if mode == "support_based":
            support_level = float(stop_loss.get("support_level", 0))
            if current_price < support_level:
                return {
                    "ticker": ticker,
                    "type": "stop_loss_breach",
                    "severity": "critical",
                    "mode": "support_based",
                    "current_price": current_price,
                    "support_level": support_level,
                    "message": (
                        f"{ticker} price ${current_price:.2f} below support "
                        f"${support_level:.2f}, stop loss triggered"
                    ),
                }
        elif mode == "fixed_pct":
            avg_cost = float(pos.get("avg_cost", 0))
            if avg_cost > 0:
                drop_pct = (avg_cost - current_price) / avg_cost
                drop_threshold = float(stop_loss.get("drop_pct_from_entry", 0.08))
                if drop_pct > drop_threshold:
                    return {
                        "ticker": ticker,
                        "type": "stop_loss_breach",
                        "severity": "critical",
                        "mode": "fixed_pct",
                        "current_price": current_price,
                        "avg_cost": avg_cost,
                        "drop_pct": round(drop_pct, 4),
                        "threshold": drop_threshold,
                        "message": (
                            f"{ticker} dropped {drop_pct:.1%} from entry "
                            f"${avg_cost:.2f}, stop loss triggered"
                        ),
                    }

        return None

    # ------------------------------------------------------------------
    # Check 2: DTE warning
    # ------------------------------------------------------------------

    @staticmethod
    def _check_dte(pos: dict[str, Any]) -> dict[str, Any] | None:
        """Warn when LEAPS DTE ≤ 90 days."""
        dte = pos.get("dte")
        if dte is None:
            return None
        dte = int(dte)
        if dte <= DTE_WARNING_DAYS:
            return {
                "ticker": pos.get("ticker", "unknown"),
                "type": "leaps_dte_warning",
                "severity": "warning",
                "dte": dte,
                "message": (
                    f"{pos.get('ticker', 'unknown')} LEAPS DTE={dte} days, "
                    f"consider roll or close"
                ),
            }
        return None

    # ------------------------------------------------------------------
    # Check 3: Theta acceleration
    # ------------------------------------------------------------------

    @staticmethod
    def _check_theta_acceleration(pos: dict[str, Any]) -> dict[str, Any] | None:
        """Detect accelerating theta decay.

        Conditions:
        - DTE < 60
        - theta absolute value > previous 5-day avg × 1.5
          OR theta / option_value > 2% daily
        """
        dte = pos.get("dte")
        if dte is None or int(dte) > THETA_ACCEL_DTE_MAX:
            return None

        theta = pos.get("theta")
        if theta is None:
            return None
        theta = abs(float(theta))

        # Check theta vs 5-day average
        theta_5d_avg = pos.get("theta_5d_avg")
        if theta_5d_avg is not None and float(theta_5d_avg) > 0:
            if theta > float(theta_5d_avg) * THETA_ACCEL_MULTIPLIER:
                return {
                    "ticker": pos.get("ticker", "unknown"),
                    "type": "theta_accelerating",
                    "severity": "warning",
                    "theta": theta,
                    "theta_5d_avg": float(theta_5d_avg),
                    "dte": int(dte),
                    "message": (
                        f"{pos.get('ticker', 'unknown')} theta acceleration: "
                        f"current {theta:.4f} > 1.5× 5d avg {float(theta_5d_avg):.4f}"
                    ),
                }

        # Check theta / option_value ratio
        option_value = pos.get("option_value")
        if option_value is not None and float(option_value) > 0:
            daily_pct = theta / float(option_value)
            if daily_pct > THETA_DAILY_PCT_MAX:
                return {
                    "ticker": pos.get("ticker", "unknown"),
                    "type": "theta_accelerating",
                    "severity": "warning",
                    "theta": theta,
                    "daily_decay_pct": round(daily_pct, 4),
                    "dte": int(dte),
                    "message": (
                        f"{pos.get('ticker', 'unknown')} theta daily decay "
                        f"{daily_pct:.1%} exceeds {THETA_DAILY_PCT_MAX:.0%} threshold"
                    ),
                }

        return None

    # ------------------------------------------------------------------
    # Check 4: Price deviation
    # ------------------------------------------------------------------

    def _check_price_deviation(
        self, state: PipelineState, ticker: str, pos: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Check if price has deviated significantly from entry."""
        current_price = self._get_current_price(state, ticker)
        if current_price is None:
            return None

        avg_cost = float(pos.get("avg_cost", 0))
        if avg_cost <= 0:
            return None

        deviation = (current_price - avg_cost) / avg_cost
        if abs(deviation) > PRICE_DEVIATION_THRESHOLD:
            direction = "above" if deviation > 0 else "below"
            return {
                "ticker": ticker,
                "type": "price_deviation",
                "severity": "info",
                "deviation_pct": round(deviation, 4),
                "current_price": current_price,
                "avg_cost": avg_cost,
                "message": (
                    f"{ticker} price {direction} entry by {abs(deviation):.1%}"
                ),
            }
        return None
