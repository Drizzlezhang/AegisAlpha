"""Research Manager Agent v2 — Recommendation ranking, triggers, add-on, cooldown, CC timing.

M2 v1.3: right-side confirmation, add-on evaluation, cooldown, conditional triggers,
CC timing guard, urgency-based ranking with daily cap.

Input: state.options_step2, state.debate_results, state.positions
Output: state.recommendations (sorted), state.pending_triggers
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, ClassVar

from jinja2 import Environment, FileSystemLoader

from aegis.agents.base import BaseAgent
from aegis.llm.client import LLMClient
from aegis.pipeline.state import PipelineState, Recommendation
from aegis.registry.agent_registry import AgentManifest

PROMPTS_DIR = Path(__file__).parent.parent.parent / "config" / "prompts"

URGENCY_WEIGHT: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}

# Default config values
DEFAULT_MAX_DAILY = 10
DEFAULT_VOLUME_MULTIPLIER = 1.5
DEFAULT_RETRACE_MAX_PCT = 0.50
DEFAULT_COOLDOWN_DAYS = 30
DEFAULT_BATCH_SPLITS = 3


class ResearchManagerAgent(BaseAgent):
    """Synthesize and rank final recommendations with v2 enhancements.

    v2 additions:
    - Right-side fake breakout filter
    - Add-on evaluation for existing positions
    - 30-day cooldown after close
    - Conditional trigger extraction (PendingTrigger)
    - CC timing guard (ranging + resistance + high IV)
    - Urgency-based ranking with daily cap
    """

    name = "research_manager"
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="research_manager",
        version="0.2.0",
        requires=["options_step2", "debate_results", "positions"],
        provides=["recommendations", "pending_triggers", "extensions.research_manager"],
        tags=["research", "ranking", "synthesis", "triggers", "cooldown"],
        llm_dependency=True,
        parallel_group=None,
        pipeline_mode="full",
    )

    def __init__(self, memory: Any, tools: dict[str, Any], config: dict[str, Any]):
        super().__init__(memory, tools, config)
        self._llm = LLMClient()
        self._jinja = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))
        rm_config = config.get("research_manager", {})
        self._max_daily = int(rm_config.get("max_daily_recommendations", DEFAULT_MAX_DAILY))
        self._volume_mult = float(rm_config.get("right_side_volume_multiplier", DEFAULT_VOLUME_MULTIPLIER))
        self._retrace_max = float(rm_config.get("right_side_retrace_max_pct", DEFAULT_RETRACE_MAX_PCT))
        self._cooldown_days = int(rm_config.get("cooldown_days", DEFAULT_COOLDOWN_DAYS))
        self._batch_splits = int(rm_config.get("batch_entry_splits", DEFAULT_BATCH_SPLITS))

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self, state: PipelineState) -> PipelineState:
        try:
            await self._synthesize(state)
        except Exception as e:
            state.error_flags.append({"agent": self.name, "error": str(e)})

        # v2: Extract conditional triggers from recommendations
        state.pending_triggers = self._extract_triggers(state)

        # v2: Rank and cap
        state.recommendations = self._rank_and_cap(state.recommendations)

        return state

    async def _synthesize(self, state: PipelineState) -> None:
        ticker = state.tickers[0] if state.tickers else "QQQ"

        positions = state.positions
        portfolio = {
            "total_nav": positions.get("total_nav", 100000.0),
            "cash": positions.get("cash", 50000.0),
            "positions": positions.get("holdings", []),
        }

        template = self._jinja.get_template("research_manager_synthesis.j2")
        prompt = template.render(
            ticker=ticker,
            options_step2=state.options_step2,
            debate_results=state.debate_results,
            portfolio=portfolio,
        )

        response = await self._llm.chat(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        try:
            result = json.loads(response["content"])
        except (json.JSONDecodeError, KeyError):
            state.error_flags.append(
                {"agent": self.name, "error": "Failed to parse LLM JSON response"}
            )
            return

        raw_recs = result.get("recommendations", [])

        recommendations: list[Recommendation] = []
        for r in raw_recs:
            rec_ticker = r.get("ticker", ticker)

            # v2: Check cooldown
            if self._in_cooldown(state, rec_ticker):
                continue

            # v2: Right-side confirmation for active_right
            entry_mode = state.entry_mode.get(rec_ticker, "")
            if entry_mode == "active_right":
                if not self._right_side_confirmed(state, rec_ticker):
                    continue

            rec = Recommendation(
                ticker=rec_ticker,
                action=r.get("action", "hold"),
                strategy=r.get("strategy", "stock"),
                rationale=r.get("rationale", ""),
                urgency=r.get("urgency", "medium"),
                score=float(r.get("score", 50)),
                delta_dollars_delta=float(r.get("delta_dollars_delta", 0)),
            )
            recommendations.append(rec)

        # v2: Add-on evaluation
        add_recs = self._build_add_recommendations(state)
        recommendations.extend(add_recs)

        # v2: CC timing evaluation
        cc_recs = await self._cc_timing(state)
        recommendations.extend(cc_recs)

        # Sort by urgency × score
        recommendations = self._sort_recommendations(recommendations)
        state.recommendations = recommendations

        self.write_extension(
            state,
            "synthesis_raw",
            {
                "total_recommendations": len(recommendations),
                "llm_model": response.get("model", "unknown"),
                "add_on_count": len(add_recs),
                "cc_count": len(cc_recs),
            },
        )

    # ------------------------------------------------------------------
    # v2: Right-side fake breakout filter
    # ------------------------------------------------------------------

    def _right_side_confirmed(self, state: PipelineState, ticker: str) -> bool:
        """Check if right-side entry passes fake breakout filter.

        Conditions:
        1. Breakout day volume > 20-day average × volume_multiplier
        2. Retrace after breakout < retrace_max_pct of breakout move
        """
        market = state.market_data.get(ticker, {})
        volume = float(market.get("volume", 0))
        avg_volume = float(market.get("avg_volume_20d", 0))

        if avg_volume > 0 and volume < avg_volume * self._volume_mult:
            return False

        # Check retrace
        retrace_pct = float(market.get("retrace_from_breakout_pct", 0))
        if retrace_pct > self._retrace_max:
            return False

        return True

    # ------------------------------------------------------------------
    # v2: Add-on evaluation
    # ------------------------------------------------------------------

    def _build_add_recommendations(self, state: PipelineState) -> list[Recommendation]:
        """Evaluate existing active positions for add-on opportunities.

        Conditions:
        - Position exists and is active (not passive)
        - Current allocation < target (20%)
        - Thesis still valid (debate direction is bullish)
        - Debate score improved vs previous
        """
        add_recs: list[Recommendation] = []
        holdings = state.positions.get("holdings", [])
        total_nav = float(state.positions.get("total_nav", 100000.0))

        for holding in holdings:
            ticker = holding.get("ticker", "")
            if not ticker:
                continue

            entry_mode = state.entry_mode.get(ticker, "")
            if entry_mode == "passive":
                continue

            current_pct = float(holding.get("position_pct", 0))
            if current_pct >= 0.20:
                continue

            debate = state.debate_results.get(ticker, {})
            if debate.get("direction") != "bullish":
                continue

            # Check if debate score improved
            prev_score = float(holding.get("prev_debate_score", 0))
            current_score = float(debate.get("confidence", 0))
            if current_score <= prev_score:
                continue

            add_recs.append(
                Recommendation(
                    ticker=ticker,
                    action="add",
                    strategy=holding.get("strategy", "stock"),
                    rationale=f"Add-on: thesis strengthening, {current_pct:.0%} → target 20%",
                    urgency="medium",
                    score=current_score * 100,
                    delta_dollars_delta=total_nav * (0.20 - current_pct) * 0.6,
                )
            )

        return add_recs

    # ------------------------------------------------------------------
    # v2: Cooldown check
    # ------------------------------------------------------------------

    def _in_cooldown(self, state: PipelineState, ticker: str) -> bool:
        """Check if ticker is in cooldown period after close.

        Returns True if the ticker was closed within cooldown_days
        and no strong reversal signal exists.
        """
        closed_positions = state.positions.get("closed_positions", [])
        now = datetime.now(timezone.utc)

        for closed in closed_positions:
            if closed.get("ticker") != ticker:
                continue
            closed_at = closed.get("closed_at", "")
            if not closed_at:
                continue
            try:
                close_time = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
                days_since = (now - close_time).days
                if days_since <= self._cooldown_days:
                    # Check for strong reversal signal
                    debate = state.debate_results.get(ticker, {})
                    if debate.get("direction") == "reversal" and debate.get("confidence", 0) > 0.80:
                        return False  # Strong reversal overrides cooldown
                    return True
            except (ValueError, TypeError):
                pass

        return False

    # ------------------------------------------------------------------
    # v2: Conditional trigger extraction
    # ------------------------------------------------------------------

    def _extract_triggers(self, state: PipelineState) -> list[dict[str, Any]]:
        """Extract conditional triggers from recommendations and S2 plans.

        Generates PendingTrigger entries for:
        - Price below support → left-side entry
        - Price above resistance → right-side entry
        - RSI below threshold → oversold bounce
        - Volume spike → breakout confirmation
        """
        triggers: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        valid_until = now + timedelta(days=7)

        for ticker in state.tickers:
            s2_data = state.options_step2.get(ticker, {})
            entry_mode = s2_data.get("entry_mode", "")
            levels = state.analyst_outputs.get("levels", {}).get(ticker, {})

            # Price-below-support trigger for active_left
            if entry_mode == "active_left":
                support_levels = levels.get("support_levels", [])
                if support_levels:
                    triggers.append({
                        "ticker": ticker,
                        "trigger_type": "price_below",
                        "trigger_params": {"threshold": support_levels[0], "comparison": "<"},
                        "suggested_action": {
                            "action": "buy",
                            "strategy": "leaps_call",
                            "entry_mode": "active_left",
                            "note": f"Left-side entry when {ticker} drops below support ${support_levels[0]}",
                        },
                        "status": "pending",
                        "created_at": now.isoformat(),
                        "valid_until": valid_until.isoformat(),
                        "fired_at": None,
                    })

            # Price-above-resistance trigger for active_right
            if entry_mode == "active_right":
                resistance_levels = levels.get("resistance_levels", [])
                if resistance_levels:
                    triggers.append({
                        "ticker": ticker,
                        "trigger_type": "price_above",
                        "trigger_params": {"threshold": resistance_levels[0], "comparison": ">"},
                        "suggested_action": {
                            "action": "buy",
                            "strategy": "leaps_call",
                            "entry_mode": "active_right",
                            "note": f"Right-side entry when {ticker} breaks above ${resistance_levels[0]}",
                        },
                        "status": "pending",
                        "created_at": now.isoformat(),
                        "valid_until": valid_until.isoformat(),
                        "fired_at": None,
                    })

            # RSI oversold trigger
            market = state.market_data.get(ticker, {})
            rsi = float(market.get("rsi_14", 50))
            if rsi < 30:
                triggers.append({
                    "ticker": ticker,
                    "trigger_type": "rsi_below",
                    "trigger_params": {"threshold": 30, "current_rsi": rsi},
                    "suggested_action": {
                        "action": "buy",
                        "strategy": "leaps_call",
                        "entry_mode": "active_left",
                        "note": f"RSI oversold at {rsi:.0f}, potential bounce",
                    },
                    "status": "pending",
                    "created_at": now.isoformat(),
                    "valid_until": valid_until.isoformat(),
                    "fired_at": None,
                })

        return triggers

    # ------------------------------------------------------------------
    # v2: CC Timing Guard
    # ------------------------------------------------------------------

    async def _cc_timing(self, state: PipelineState) -> list[Recommendation]:
        """Evaluate whether conditions are right for Covered Call selling.

        Three conditions must ALL be met:
        1. Ranging market (trend not strongly directional)
        2. Technical resistance confirmed (Level Analyst)
        3. IV elevated (IV percentile > 50%)
        """
        cc_recs: list[Recommendation] = []

        for ticker in state.tickers:
            entry_mode = state.entry_mode.get(ticker, "")
            if entry_mode != "cc":
                continue

            # Check trend: must be ranging
            trend = state.analyst_outputs.get("trend", {}).get(ticker, {})
            phase = trend.get("phase", "").lower()
            if phase not in ("ranging", "sideways", "distribution"):
                continue

            # Check resistance
            levels = state.analyst_outputs.get("levels", {}).get(ticker, {})
            resistance_levels = levels.get("resistance_levels", [])
            if not resistance_levels:
                continue

            # Check IV
            s1_data = state.options_step1.get(ticker, {})
            iv_data = s1_data.get("iv_data", {})
            iv_percentile = iv_data.get("percentile", 0.0)
            if iv_percentile <= 0.50:
                continue

            # All conditions met → CC recommendation
            cc_recs.append(
                Recommendation(
                    ticker=ticker,
                    action="sell",
                    strategy="covered_call",
                    rationale=(
                        f"CC timing: ranging market, resistance at ${resistance_levels[0]}, "
                        f"IV percentile {iv_percentile:.0%}"
                    ),
                    urgency="medium",
                    score=65.0,
                    delta_dollars_delta=-200.0,
                )
            )

        return cc_recs

    # ------------------------------------------------------------------
    # v2: Ranking and daily cap
    # ------------------------------------------------------------------

    def _rank_and_cap(self, recs: list[Recommendation]) -> list[Recommendation]:
        """Rank recommendations by urgency priority, then cap at max_daily.

        Priority order:
        1. Stop-loss alerts (urgency: critical)
        2. Close reminders (urgency: high)
        3. Add-on opportunities (urgency: medium)
        4. New opportunities (urgency: normal/low)

        Within same urgency, sort by score descending.
        """
        # Sort by urgency weight × score
        sorted_recs = sorted(
            recs,
            key=lambda r: URGENCY_WEIGHT.get(r.urgency, 2) * r.score,
            reverse=True,
        )

        # Cap at max_daily
        return sorted_recs[: self._max_daily]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sort_recommendations(recs: list[Recommendation]) -> list[Recommendation]:
        return sorted(
            recs,
            key=lambda r: URGENCY_WEIGHT.get(r.urgency, 2) * r.score,
            reverse=True,
        )
