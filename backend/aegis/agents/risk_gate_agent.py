"""Risk Gate Agent v2 — Pure rule engine for trade safety checks.

M2 v1.3: Delta Dollars incremental budget + IV crush guard.

Input: state.recommendations, state.positions, state.market_data, state.macro_data
Output: state.recommendations (passed), state.blocked_recommendations (blocked)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, cast

import yaml

from aegis.agents.base import BaseAgent
from aegis.pipeline.state import BlockedRecommendation, PipelineState, Recommendation
from aegis.registry.agent_registry import AgentManifest

RULES_PATH = Path(__file__).parent.parent.parent / "config" / "rules.yaml"

DEFAULT_MAX_POSITION_PCT = 0.80
DEFAULT_MIN_CASH_PCT = 0.20
DEFAULT_LEAPS_MIN_DTE = 360
DEFAULT_VIX_MAX = 30
DEFAULT_VIX_DAILY_CHANGE_MAX = 0.20
DEFAULT_FOMC_BLACKOUT_HOURS = 24
DEFAULT_EARNINGS_BLACKOUT_HOURS = 48
DEFAULT_DELTA_BUDGET_PCT = 0.30
DEFAULT_IV_CRUSH_THRESHOLD = "high"


class RiskGateAgent(BaseAgent):
    """Pure rule engine — checks 10 rules against each recommendation.

    No LLM dependency. Rules are checked in order; first violation blocks
    the recommendation. Blocked recommendations are moved to
    state.blocked_recommendations with a block_reason.

    v2 additions:
    - Rule 9: Delta Dollars incremental budget
    - Rule 10: IV crush guard
    """

    name = "risk_gate"
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="risk_gate",
        version="0.2.0",
        requires=["recommendations", "positions", "market_data", "macro_data"],
        provides=["recommendations", "blocked_recommendations", "extensions.risk_gate"],
        tags=["risk", "gate", "safety", "delta_budget", "iv_crush"],
        llm_dependency=False,
        parallel_group=None,
        pipeline_mode="full",
    )

    def __init__(self, memory: Any, tools: dict[str, Any], config: dict[str, Any]):
        super().__init__(memory, tools, config)
        self._rules: dict[str, Any] = self._load_rules()

    def _load_rules(self) -> dict[str, Any]:
        """Load risk gate rules from rules.yaml, with defaults fallback."""
        try:
            with open(RULES_PATH) as f:
                data: dict[str, Any] = yaml.safe_load(f)
            return cast(dict[str, Any], data.get("rules", {}).get("risk_gate", {}))
        except Exception:
            return {}

    def _get_rule(self, key: str, default: float) -> float:
        return float(self._rules.get(key, default))

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self, state: PipelineState) -> PipelineState:
        passed: list[Recommendation] = []
        blocked: list[BlockedRecommendation] = []

        for rec in state.recommendations:
            reason = self._check_rules(rec, state)
            if reason:
                blocked.append(
                    BlockedRecommendation(
                        recommendation=rec,
                        block_reason=reason,
                    )
                )
            else:
                passed.append(rec)

        # v2: Apply Delta Dollars incremental budget (second pass)
        passed = self._apply_delta_budget(passed, state, blocked)

        state.recommendations = passed
        state.blocked_recommendations = blocked

        self.write_extension(
            state,
            "summary",
            {
                "total_checked": len(passed) + len(blocked),
                "passed": len(passed),
                "blocked": len(blocked),
            },
        )

        return state

    def _check_rules(self, rec: Recommendation, state: PipelineState) -> str | None:
        """Check all 10 rules in order. Returns first block reason or None."""
        checks = [
            self._check_position_limit,
            self._check_cash_minimum,
            self._check_blacklist,
            self._check_leaps_dte,
            self._check_vix,
            self._check_fomc_blackout,
            self._check_earnings_blackout,
            self._check_support_based_stop_loss,
            self._check_iv_crush,  # v2: Rule 9
        ]
        for check in checks:
            reason = check(rec, state)
            if reason:
                return reason
        return None

    # ------------------------------------------------------------------
    # Rule 1: Position limit (> 80% → block buy/add)
    # ------------------------------------------------------------------

    def _check_position_limit(self, rec: Recommendation, state: PipelineState) -> str | None:
        if rec.action not in ("buy", "add"):
            return None
        max_pct = self._get_rule("max_total_position_pct", DEFAULT_MAX_POSITION_PCT)
        total_pct = float(state.positions.get("total_position_pct", 0.0))
        if total_pct > max_pct:
            return f"Position limit exceeded: {total_pct:.0%} > {max_pct:.0%}"
        return None

    # ------------------------------------------------------------------
    # Rule 2: Cash minimum (< 20% → block buy/add)
    # ------------------------------------------------------------------

    def _check_cash_minimum(self, rec: Recommendation, state: PipelineState) -> str | None:
        if rec.action not in ("buy", "add"):
            return None
        min_cash = self._get_rule("min_cash_pct", DEFAULT_MIN_CASH_PCT)
        total_nav = float(state.positions.get("total_nav", 0.0))
        cash = float(state.positions.get("cash", 0.0))
        if total_nav > 0 and (cash / total_nav) < min_cash:
            return f"Cash below minimum: {cash / total_nav:.0%} < {min_cash:.0%}"
        return None

    # ------------------------------------------------------------------
    # Rule 3: Blacklist ticker → block any recommendation
    # ------------------------------------------------------------------

    def _check_blacklist(self, rec: Recommendation, state: PipelineState) -> str | None:
        blacklist: list[str] = self._rules.get("blacklist_tickers", [])
        if rec.ticker in blacklist:
            return f"Ticker {rec.ticker} is blacklisted"
        return None

    # ------------------------------------------------------------------
    # Rule 4: LEAPS DTE < 12 months → block LEAPS Call new position
    # ------------------------------------------------------------------

    def _check_leaps_dte(self, rec: Recommendation, state: PipelineState) -> str | None:
        if rec.strategy != "leaps_call":
            return None
        if rec.action not in ("buy", "add"):
            return None
        min_dte = int(self._get_rule("leaps_min_dte", DEFAULT_LEAPS_MIN_DTE))
        for contract in rec.option_contracts:
            if contract.dte < min_dte:
                return f"LEAPS DTE too short: {contract.dte}d < {min_dte}d minimum"
        return None

    # ------------------------------------------------------------------
    # Rule 5: VIX > 30 or daily change > 20% → block all new positions
    # ------------------------------------------------------------------

    def _check_vix(self, rec: Recommendation, state: PipelineState) -> str | None:
        if rec.action not in ("buy", "add"):
            return None
        vix_max = self._get_rule("vix_max", DEFAULT_VIX_MAX)
        vix_change_max = self._get_rule("vix_daily_change_max_pct", DEFAULT_VIX_DAILY_CHANGE_MAX)

        market = state.market_data.get(rec.ticker, {})
        vix = float(market.get("vix", 0.0))
        vix_change = float(market.get("vix_daily_change_pct", 0.0))

        if vix > vix_max:
            return f"VIX too high: {vix} > {vix_max}"
        if vix_change > vix_change_max:
            return f"VIX daily spike: {vix_change:.0%} > {vix_change_max:.0%}"
        return None

    # ------------------------------------------------------------------
    # Rule 6: FOMC/CPI/NFP within 24h → block LEAPS Call new position
    # ------------------------------------------------------------------

    def _check_fomc_blackout(self, rec: Recommendation, state: PipelineState) -> str | None:
        if rec.strategy != "leaps_call":
            return None
        if rec.action not in ("buy", "add"):
            return None
        blackout_hours = self._get_rule("fomc_blackout_hours", DEFAULT_FOMC_BLACKOUT_HOURS)

        fomc_raw = state.macro_data.get("fomc_meeting")
        if fomc_raw is None:
            return None

        fomc_time = self._parse_datetime(fomc_raw)
        if fomc_time is None:
            return None

        now = datetime.now(UTC)
        hours_until = (fomc_time - now).total_seconds() / 3600
        if 0 < hours_until <= blackout_hours:
            return f"FOMC blackout: {hours_until:.0f}h until meeting"
        return None

    # ------------------------------------------------------------------
    # Rule 7: Earnings within 48h → block that ticker's new position
    # ------------------------------------------------------------------

    def _check_earnings_blackout(self, rec: Recommendation, state: PipelineState) -> str | None:
        if rec.action not in ("buy", "add"):
            return None
        blackout_hours = self._get_rule("earnings_blackout_hours", DEFAULT_EARNINGS_BLACKOUT_HOURS)

        earnings: dict[str, Any] = state.macro_data.get("next_earnings", {})
        earnings_time_raw = earnings.get(rec.ticker)
        if earnings_time_raw is None:
            return None

        earnings_time = self._parse_datetime(earnings_time_raw)
        if earnings_time is None:
            return None

        now = datetime.now(UTC)
        hours_until = (earnings_time - now).total_seconds() / 3600
        if 0 < hours_until <= blackout_hours:
            return f"Earnings blackout: {hours_until:.0f}h until {rec.ticker} earnings"
        return None

    # ------------------------------------------------------------------
    # Rule 8: Support-based stop loss required for active_left
    # ------------------------------------------------------------------

    def _check_support_based_stop_loss(
        self, rec: Recommendation, state: PipelineState
    ) -> str | None:
        if rec.action not in ("buy", "add"):
            return None
        entry_mode = state.entry_mode.get(rec.ticker, "")
        if entry_mode != "active_left":
            return None
        stop_loss = rec.stop_loss
        if not stop_loss or stop_loss.get("method") != "support_based":
            return "Support-based stop loss required for active_left entry mode"
        return None

    # ------------------------------------------------------------------
    # v2 Rule 9: IV crush guard
    # ------------------------------------------------------------------

    def _check_iv_crush(self, rec: Recommendation, state: PipelineState) -> str | None:
        """Block recommendations when IV crush risk is high.

        Reads IV crush risk from Options Strategist S1 output.
        Blocks if level == "high" (configurable threshold).
        """
        if rec.action not in ("buy", "add"):
            return None

        threshold = self._rules.get("iv_crush_block_threshold", DEFAULT_IV_CRUSH_THRESHOLD)
        s1_data = state.options_step1.get(rec.ticker, {})
        iv_crush = s1_data.get("iv_crush_risk", {})

        if iv_crush.get("level") == threshold:
            event = iv_crush.get("upcoming_event", "unknown event")
            days = iv_crush.get("days_until_event", "?")
            return f"IV crush risk high: {event} in {days}d"

        return None

    # ------------------------------------------------------------------
    # v2 Rule 10: Delta Dollars incremental budget (second pass)
    # ------------------------------------------------------------------

    def _apply_delta_budget(
        self,
        passed: list[Recommendation],
        state: PipelineState,
        blocked: list[BlockedRecommendation],
    ) -> list[Recommendation]:
        """Apply Delta Dollars incremental budget constraint.

        Total delta_dollars_delta of passed recommendations must not exceed
        NAV × budget_pct. Low-score recommendations are moved to blocked
        if budget is exceeded.
        """
        budget_pct = float(self._rules.get("delta_dollars_budget_pct", DEFAULT_DELTA_BUDGET_PCT))
        total_nav = float(state.positions.get("total_nav", 100000.0))
        budget_usd = total_nav * budget_pct

        # Sort by score descending (highest priority first)
        sorted_recs = sorted(passed, key=lambda r: r.score, reverse=True)

        kept: list[Recommendation] = []
        used: float = 0.0

        for rec in sorted_recs:
            delta = abs(rec.delta_dollars_delta)
            if used + delta <= budget_usd:
                kept.append(rec)
                used += delta
            else:
                blocked.append(
                    BlockedRecommendation(
                        recommendation=rec,
                        block_reason=f"Delta budget exceeded: ${used:.0f} used of ${budget_usd:.0f} ({(used + delta) / total_nav:.0%} > {budget_pct:.0%})",
                    )
                )

        return kept

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse a datetime from string or return as-is if already datetime."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return None
        return None
