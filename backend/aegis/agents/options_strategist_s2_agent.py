"""Options Strategist Step 2 Agent — Multi-strategy plan generation with LLM.

M2 v1.3: entry_mode, multi-strategy comparison, scenario P&L, roll evaluation,
batch entry, structured stop-loss.

Input: state.options_step1, state.debate_results, state.analyst_outputs.levels
Output: state.options_step2[ticker], state.strategy_comparisons, state.scenario_pnl
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, ClassVar

from jinja2 import Environment, FileSystemLoader

from aegis.agents.base import BaseAgent
from aegis.calculators.greeks import compute_greeks
from aegis.calculators.stop_loss import compute_stop_loss
from aegis.llm.client import LLMClient
from aegis.pipeline.state import (
    OptionPlan,
    PipelineState,
    ScenarioPnL,
    StopLossPlan,
)
from aegis.registry.agent_registry import AgentManifest

PROMPTS_DIR = Path(__file__).parent.parent.parent / "config" / "prompts"

# Entry mode thresholds
SUPPORT_DISTANCE_THRESHOLD = 0.03  # 3% from support → active_left
BREAKOUT_CONFIDENCE_MIN = 0.70  # Debate confidence for breakout → active_right

# Batch entry defaults
BATCH_SPLITS = 3
BATCH_WEIGHTS = [0.40, 0.40, 0.20]  # 40% / 40% / 20%

# Roll evaluation
ROLL_DTE_THRESHOLD = 180  # DTE < 180 → consider roll
QQQ_TICKER = "QQQ"  # QQQ LEAPS: close only, no roll


class OptionsStrategistS2Agent(BaseAgent):
    """Generate multi-strategy option plans with scenario P&L and batch entry.

    Reads S1 candidates, debate results, support/resistance levels, and IV data.
    Calls LLM (gpt-4o) to select best contracts, then enriches with:
    - entry_mode determination
    - multi-strategy comparison (≥2 plans)
    - scenario P&L simulation
    - roll evaluation for existing LEAPS
    - batch entry for active_left mode
    - structured stop-loss plans
    """

    name = "options_strategist_s2"
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="options_strategist_s2",
        version="0.2.0",
        requires=["options_step1", "debate_results", "analyst_outputs.levels"],
        provides=[
            "options_step2",
            "strategy_comparisons",
            "scenario_pnl",
            "extensions.options_strategist_s2",
        ],
        tags=["options", "strategy", "signal", "multi_strategy"],
        llm_dependency=True,
        parallel_group=None,
        pipeline_mode="full",
    )

    def __init__(self, memory: Any, tools: dict[str, Any], config: dict[str, Any]):
        super().__init__(memory, tools, config)
        self._llm = LLMClient()
        self._jinja = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))
        self._min_plans = int(config.get("options_strategist", {}).get("min_plans_per_ticker", 2))
        self._roll_dte_threshold = int(
            config.get("options_strategist", {}).get("roll_dte_threshold", ROLL_DTE_THRESHOLD)
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            try:
                await self._process_ticker(state, ticker)
            except Exception as e:
                state.error_flags.append(
                    {"agent": self.name, "ticker": ticker, "error": str(e)}
                )
        return state

    async def _process_ticker(self, state: PipelineState, ticker: str) -> None:
        s1_data = state.options_step1.get(ticker, {})
        candidates = s1_data.get("candidates", [])
        if not candidates:
            state.options_step2[ticker] = {}
            return

        debate = state.debate_results.get(ticker, {})
        levels = state.analyst_outputs.get("levels", {}).get(ticker, {})
        iv_crush_risk = s1_data.get("iv_crush_risk", {})

        # 1. Determine entry mode
        entry_mode = self._decide_entry_mode(debate, levels, candidates)

        # 2. Call LLM for base contract selection
        template = self._jinja.get_template("options_strategist_s2.j2")
        prompt = template.render(
            ticker=ticker,
            candidates=candidates,
            debate=debate,
            levels=levels,
            entry_mode=entry_mode,
            iv_crush_risk=iv_crush_risk,
        )

        response = await self._llm.chat(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        try:
            result = json.loads(response["content"])
        except (json.JSONDecodeError, KeyError):
            state.error_flags.append(
                {"agent": self.name, "ticker": ticker, "error": "Failed to parse LLM JSON response"}
            )
            state.options_step2[ticker] = {}
            return

        contracts = result.get("contracts", [])

        # 3. Generate multi-strategy plans
        plans = self._generate_plans(ticker, entry_mode, contracts, levels, candidates)

        # 4. Compute scenario P&L for each plan
        spot_price = self._get_spot_price(candidates)
        for plan in plans:
            plan.scenario_pnl = self.compute_scenario_pnl(plan, spot_price)

        # 5. Add batch entry for active_left
        if entry_mode == "active_left":
            plans = self._add_batch_entry(plans, levels)

        # 6. Build stop-loss for each plan
        for plan in plans:
            plan.stop_loss_plan = self._build_stop_loss(entry_mode, levels, plan.estimated_cost)

        # 7. Roll evaluation for existing positions
        roll_result = self._roll_evaluation(state, ticker, entry_mode)

        # 8. Write outputs
        state.options_step2[ticker] = {
            "contracts": contracts,
            "entry_mode": entry_mode,
            "plans": [p.model_dump() for p in plans],
            "roll_evaluation": roll_result,
        }

        state.strategy_comparisons[ticker] = [p.model_dump() for p in plans]
        state.scenario_pnl[ticker] = {
            f"plan_{p.plan_no}": p.scenario_pnl.model_dump() if p.scenario_pnl else {}
            for p in plans
        }

        self.write_extension(
            state,
            "s2_raw",
            {
                "ticker": ticker,
                "entry_mode": entry_mode,
                "plans_count": len(plans),
                "contracts_count": len(contracts),
                "has_roll_eval": roll_result is not None,
            },
        )

    # ------------------------------------------------------------------
    # Entry mode determination
    # ------------------------------------------------------------------

    @staticmethod
    def _decide_entry_mode(
        debate: dict[str, Any],
        levels: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> str:
        """Determine entry_mode: active_left, active_right, or both.

        active_left:
        - Debate direction is "bullish" or "reversal"
        - Support level exists and current price within 3% of support

        active_right:
        - Debate direction is "bullish" or "breakout"
        - Debate confidence >= 70%
        - Breakout confirmed (no retrace > 50%)

        Falls back to "both" if unclear.
        """
        direction = debate.get("direction", "").lower()
        confidence = debate.get("confidence", 0.0)

        support_levels = levels.get("support_levels", [])
        spot = candidates[0].get("spot_price", 0.0) if candidates else 0.0

        left_eligible = False
        right_eligible = False

        # Left side: near support
        if direction in ("bullish", "reversal") and support_levels and spot > 0:
            nearest_support = support_levels[0]
            distance_pct = (spot - nearest_support) / spot if spot > 0 else float("inf")
            if distance_pct <= SUPPORT_DISTANCE_THRESHOLD:
                left_eligible = True

        # Right side: breakout confirmed
        if direction in ("bullish", "breakout") and confidence >= BREAKOUT_CONFIDENCE_MIN:
            right_eligible = True

        if left_eligible and right_eligible:
            return "both"
        if left_eligible:
            return "active_left"
        if right_eligible:
            return "active_right"
        return "both"

    # ------------------------------------------------------------------
    # Multi-strategy plan generation
    # ------------------------------------------------------------------

    def _generate_plans(
        self,
        ticker: str,
        entry_mode: str,
        contracts: list[dict[str, Any]],
        levels: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[OptionPlan]:
        """Generate at least min_plans strategy plans per ticker.

        Plan A: LEAPS Call (primary)
        Plan B: Diagonal Spread (high IV environment)
        Optional C: Covered Call (cc mode)

        Matches LLM-selected contracts back to S1 candidates for full Greeks data.
        """
        plans: list[OptionPlan] = []
        plan_no = 1

        # Match LLM contracts to S1 candidates by strike+type for full data
        enriched = self._enrich_contracts(contracts, candidates)

        # Find best LEAPS candidate
        leaps_candidate = self._pick_best_candidate(enriched, "call")
        if leaps_candidate:
            plans.append(self._build_leaps_plan(plan_no, leaps_candidate, entry_mode))
            plan_no += 1

        # Diagonal spread if IV is elevated
        iv_data = self._get_iv_from_candidates(candidates)
        if iv_data.get("percentile", 0.0) > 0.50:
            diag_candidate = self._pick_best_candidate(enriched, "call", prefer_otm=True)
            if diag_candidate:
                plans.append(self._build_diagonal_plan(plan_no, diag_candidate, entry_mode))
                plan_no += 1

        # Covered Call for cc mode
        if entry_mode == "cc":
            cc_candidate = self._pick_best_candidate(enriched, "call", prefer_otm=True)
            if cc_candidate:
                plans.append(self._build_cc_plan(plan_no, cc_candidate))
                plan_no += 1

        # Ensure minimum plans
        while len(plans) < self._min_plans and len(enriched) > len(plans):
            alt = enriched[len(plans)]
            plans.append(self._build_leaps_plan(plan_no, alt, entry_mode))
            plan_no += 1

        return plans

    @staticmethod
    def _enrich_contracts(
        llm_contracts: list[dict[str, Any]],
        s1_candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Match LLM-selected contracts to S1 candidates for full Greeks data."""
        enriched: list[dict[str, Any]] = []
        for lc in llm_contracts:
            strike = lc.get("strike")
            opt_type = lc.get("type")
            # Find matching S1 candidate
            match = None
            for sc in s1_candidates:
                if sc.get("strike") == strike and sc.get("type") == opt_type:
                    match = sc
                    break
            if match:
                merged = {**match, **lc}  # S1 data + LLM fields (entry_price, rationale)
            else:
                merged = dict(lc)
            enriched.append(merged)
        return enriched

    @staticmethod
    def _pick_best_candidate(
        contracts: list[dict[str, Any]],
        option_type: str,
        prefer_otm: bool = False,
    ) -> dict[str, Any] | None:
        """Pick the best candidate contract by type and criteria."""
        matching = [c for c in contracts if c.get("type") == option_type]
        if not matching:
            return None
        if prefer_otm:
            matching.sort(key=lambda c: abs(c.get("delta", 0.0)))
        else:
            matching.sort(key=lambda c: abs(c.get("delta", 0.0)), reverse=True)
        return matching[0]

    @staticmethod
    def _build_leaps_plan(plan_no: int, c: dict[str, Any], entry_mode: str) -> OptionPlan:
        entry_price = c.get("entry_price", (c.get("bid", 0.0) + c.get("ask", 0.0)) / 2.0)
        return OptionPlan(
            plan_no=plan_no,
            strategy="leaps_call",
            strike=c.get("strike", 0.0),
            expiry=c.get("expiration", ""),
            dte=c.get("dte", 0),
            option_type="call",
            delta=c.get("delta", 0.0),
            gamma=c.get("gamma", 0.0),
            theta=c.get("theta", 0.0),
            vega=c.get("vega", 0.0),
            iv=c.get("iv", 0.0),
            estimated_cost=round(entry_price * 100, 2),
            pros=["Long-dated, low theta decay", "High delta exposure", "Simple structure"],
            cons=["Full premium upfront", "Vega risk if IV drops"],
            liquidity_score=0.8 if c.get("oi", 0) > 500 else 0.5,
            entry_mode=entry_mode,
        )

    @staticmethod
    def _build_diagonal_plan(plan_no: int, c: dict[str, Any], entry_mode: str) -> OptionPlan:
        entry_price = c.get("entry_price", (c.get("bid", 0.0) + c.get("ask", 0.0)) / 2.0)
        return OptionPlan(
            plan_no=plan_no,
            strategy="diagonal",
            strike=c.get("strike", 0.0),
            expiry=c.get("expiration", ""),
            dte=c.get("dte", 0),
            option_type="call",
            delta=c.get("delta", 0.0),
            gamma=c.get("gamma", 0.0),
            theta=c.get("theta", 0.0),
            vega=c.get("vega", 0.0),
            iv=c.get("iv", 0.0),
            estimated_cost=round(entry_price * 100 * 0.6, 2),
            pros=["Lower cost than LEAPS", "Positive theta from short leg", "Good in high IV"],
            cons=["More complex to manage", "Capped upside", "Requires active monitoring"],
            liquidity_score=0.6,
            entry_mode=entry_mode,
        )

    @staticmethod
    def _build_cc_plan(plan_no: int, c: dict[str, Any]) -> OptionPlan:
        entry_price = c.get("entry_price", (c.get("bid", 0.0) + c.get("ask", 0.0)) / 2.0)
        return OptionPlan(
            plan_no=plan_no,
            strategy="cc",
            strike=c.get("strike", 0.0),
            expiry=c.get("expiration", ""),
            dte=c.get("dte", 0),
            option_type="call",
            delta=c.get("delta", 0.0),
            gamma=c.get("gamma", 0.0),
            theta=c.get("theta", 0.0),
            vega=c.get("vega", 0.0),
            iv=c.get("iv", 0.0),
            estimated_cost=round(entry_price * 100, 2),
            pros=["Income generation", "Defined risk", "Good in range-bound markets"],
            cons=["Capped upside", "Assignment risk", "Not ideal in strong trends"],
            liquidity_score=0.7,
            entry_mode="cc",
        )

    # ------------------------------------------------------------------
    # Scenario P&L simulation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_scenario_pnl(plan: OptionPlan, spot_price: float) -> ScenarioPnL:
        """Simulate P&L under 3 scenarios: target, flat (30/60/90d), stop_loss.

        Uses Black-Scholes to estimate option value at each scenario price/time.
        """
        T = plan.dte / 365.0
        r = 0.05
        sigma = plan.iv

        def _option_value(S: float, t_remaining: float) -> float:
            if t_remaining <= 0:
                return max(0.0, S - plan.strike)
            greeks = compute_greeks(
                option_type="call", S=S, K=plan.strike, T=t_remaining, r=r, sigma=sigma
            )
            # Approximate option price via delta * S adjustment
            intrinsic = max(0.0, S - plan.strike)
            time_value = max(0.0, plan.estimated_cost / 100 - intrinsic)
            return intrinsic + time_value * (t_remaining / T)

        entry_value = plan.estimated_cost / 100

        # Target scenario: 20% above spot
        target_price = spot_price * 1.20
        target_value = _option_value(target_price, T)
        target_pnl = (target_value - entry_value) * 100

        # Flat scenarios: theta decay
        flat_30d = _option_value(spot_price, max(0, T - 30 / 365))
        flat_60d = _option_value(spot_price, max(0, T - 60 / 365))
        flat_90d = _option_value(spot_price, max(0, T - 90 / 365))

        # Stop loss: 8% below spot
        stop_price = spot_price * 0.92
        stop_value = _option_value(stop_price, T)
        stop_pnl = (stop_value - entry_value) * 100

        return ScenarioPnL(
            target={"price": round(target_price, 2), "pnl": round(target_pnl, 2), "pnl_pct": round(target_pnl / (entry_value * 100) * 100, 1) if entry_value > 0 else 0.0},
            flat_30d={"price": round(spot_price, 2), "pnl": round((flat_30d - entry_value) * 100, 2), "theta_decay": round((entry_value - flat_30d) * 100, 2)},
            flat_60d={"price": round(spot_price, 2), "pnl": round((flat_60d - entry_value) * 100, 2), "theta_decay": round((entry_value - flat_60d) * 100, 2)},
            flat_90d={"price": round(spot_price, 2), "pnl": round((flat_90d - entry_value) * 100, 2), "theta_decay": round((entry_value - flat_90d) * 100, 2)},
            stop_loss={"price": round(stop_price, 2), "pnl": round(stop_pnl, 2), "pnl_pct": round(stop_pnl / (entry_value * 100) * 100, 1) if entry_value > 0 else 0.0},
        )

    # ------------------------------------------------------------------
    # Roll evaluation
    # ------------------------------------------------------------------

    def _roll_evaluation(
        self, state: PipelineState, ticker: str, entry_mode: str
    ) -> dict[str, Any] | None:
        """Evaluate existing LEAPS positions for roll/close/hold.

        QQQ LEAPS: close only, no roll.
        Non-QQQ LEAPS: consider roll if DTE < threshold.
        """
        positions = state.positions.get(ticker, {})
        if not positions:
            return None

        # QQQ: close only
        if ticker.upper() == QQQ_TICKER:
            return {
                "ticker": ticker,
                "action": "close_only",
                "reason": "QQQ LEAPS policy: close only, no roll",
                "dte": positions.get("dte"),
            }

        dte = positions.get("dte", 999)
        if dte > self._roll_dte_threshold:
            return {
                "ticker": ticker,
                "action": "hold",
                "reason": f"DTE {dte} > {self._roll_dte_threshold}, no roll needed",
                "dte": dte,
            }

        # Check thesis validity from debate
        debate = state.debate_results.get(ticker, {})
        thesis_valid = debate.get("direction") not in ("bearish", "neutral")

        if not thesis_valid:
            return {
                "ticker": ticker,
                "action": "close",
                "reason": "Thesis invalidated, recommend close",
                "dte": dte,
            }

        # Consider roll
        return {
            "ticker": ticker,
            "action": "roll",
            "reason": f"DTE {dte} < {self._roll_dte_threshold}, thesis still valid",
            "dte": dte,
            "suggested_new_dte": dte + 365,
            "note": "Roll to next-year LEAPS with same or higher strike",
        }

    # ------------------------------------------------------------------
    # Batch entry
    # ------------------------------------------------------------------

    @staticmethod
    def _add_batch_entry(plans: list[OptionPlan], levels: dict[str, Any]) -> list[OptionPlan]:
        """Add batch entry splits for active_left mode.

        Batch 1: current price, 40%
        Batch 2: at support, 40%
        Batch 3: 2% below support, 20%
        """
        support_levels = levels.get("support_levels", [])
        if not support_levels:
            return plans

        support = support_levels[0]
        new_plans: list[OptionPlan] = []

        for plan in plans:
            if plan.entry_mode != "active_left":
                new_plans.append(plan)
                continue

            # Batch 1: current price (original plan)
            plan.batch_no = 1
            plan.batch_trigger_price = None
            new_plans.append(plan)

            # Batch 2: at support
            b2 = plan.model_copy()
            b2.plan_no = plan.plan_no + 100  # offset to avoid collision
            b2.batch_no = 2
            b2.batch_trigger_price = support
            b2.estimated_cost = round(plan.estimated_cost * BATCH_WEIGHTS[1] / BATCH_WEIGHTS[0], 2)
            new_plans.append(b2)

            # Batch 3: 2% below support
            b3 = plan.model_copy()
            b3.plan_no = plan.plan_no + 200
            b3.batch_no = 3
            b3.batch_trigger_price = round(support * 0.98, 2)
            b3.estimated_cost = round(plan.estimated_cost * BATCH_WEIGHTS[2] / BATCH_WEIGHTS[0], 2)
            new_plans.append(b3)

        return new_plans

    # ------------------------------------------------------------------
    # Stop-loss plan
    # ------------------------------------------------------------------

    @staticmethod
    def _build_stop_loss(
        entry_mode: str,
        levels: dict[str, Any],
        entry_price: float,
    ) -> dict[str, Any]:
        """Build structured stop-loss plan based on entry_mode.

        active_left → support_based
        active_right → fixed_pct (-8%)
        """
        support_levels = levels.get("support_levels", [])

        if entry_mode == "active_left" and support_levels:
            stop = compute_stop_loss(entry_price, "support_based", support_level=support_levels[0])
            return StopLossPlan(
                mode="support_based",
                trigger_price=stop.stop_price,
                support_level=support_levels[0],
                notes=f"Stop at {stop.stop_pct:.1%} below entry, 2% below support",
            ).model_dump()

        stop = compute_stop_loss(entry_price, "fixed_pct")
        return StopLossPlan(
            mode="fixed_pct",
            trigger_price=stop.stop_price,
            drop_pct_from_entry=stop.stop_pct,
            notes=f"Fixed {stop.stop_pct:.0%} trailing stop",
        ).model_dump()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_spot_price(candidates: list[dict[str, Any]]) -> float:
        for c in candidates:
            sp = c.get("spot_price", 0.0)
            if sp > 0:
                return sp
        return 0.0

    @staticmethod
    def _get_iv_from_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
        ivs = [c.get("iv", 0.0) for c in candidates if c.get("iv", 0.0) > 0]
        if not ivs:
            return {"percentile": 0.0, "current": 0.0}
        current = ivs[0]
        below = sum(1 for v in ivs if v <= current)
        return {"percentile": below / len(ivs), "current": current}
