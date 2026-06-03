"""Debate Agent — multi-round Bull vs Bear debate with Judge verdict.

Input: state.analyst_outputs[ticker] containing factor_scores
Output: state.debate_results[ticker] with direction/confidence/rationale/rounds_used
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from aegis.agents.base import BaseAgent
from aegis.llm.client import LLMClient
from aegis.pipeline.state import PipelineState
from aegis.registry.agent_registry import AgentManifest
from aegis.utils.settings import settings


class DebateAgent(BaseAgent):
    """Multi-round Bull vs Bear debate with Judge verdict."""

    name = "debate_agent"
    manifest = AgentManifest(
        name="debate_agent",
        version="0.1.0",
        requires=["analyst_outputs"],
        provides=["debate_results"],
        tags=["debate", "signal"],
        llm_dependency=True,
        pipeline_mode="full",
    )

    def __init__(
        self,
        memory: Any,
        tools: dict[str, Any],
        config: dict[str, Any],
    ) -> None:
        super().__init__(memory, tools, config)
        self.llm = LLMClient()
        templates_dir = Path(__file__).parent.parent.parent / "config" / "prompts"
        self._jinja = Environment(loader=FileSystemLoader(str(templates_dir)))
        self.max_rounds: int = int(config.get("max_rounds", 3))

    async def run(self, state: PipelineState) -> PipelineState:
        """Execute debate for each ticker with analyst outputs."""
        start_time = time.monotonic()
        total_tokens = 0

        for ticker in state.tickers:
            try:
                result, tokens = await self._debate_ticker(ticker, state)
                total_tokens += tokens
                if result is not None:
                    state.debate_results[ticker] = result
            except Exception:
                logger.exception("DebateAgent failed for ticker=%s", ticker)
                state.error_flags.append({
                    "agent": self.name,
                    "ticker": ticker,
                    "error": "DebateAgent unhandled exception",
                })

        elapsed = time.monotonic() - start_time
        state.agent_timings[self.name] = elapsed
        self.write_extension(state, "total_tokens", total_tokens)
        return state

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _debate_ticker(
        self, ticker: str, state: PipelineState
    ) -> tuple[dict[str, Any] | None, int]:
        """Run debate rounds for a single ticker. Returns (result, total_tokens)."""
        factor_scores = self._get_factor_scores(ticker, state)
        debate_history: list[dict[str, Any]] = []
        total_tokens = 0
        prev_direction: str | None = None
        consecutive_same = 0
        last_verdict: dict[str, Any] | None = None

        for round_num in range(1, self.max_rounds + 1):
            # --- Bull ---
            bull_arg, bt = await self._call_bull(ticker, factor_scores, debate_history)
            total_tokens += bt

            # --- Bear ---
            bear_arg, bet = await self._call_bear(ticker, factor_scores, debate_history)
            total_tokens += bet

            # --- Judge ---
            verdict, jt = await self._call_judge(
                ticker, factor_scores, debate_history,
                bull_arg, bear_arg, round_num,
            )
            total_tokens += jt

            if verdict is None:
                # JSON parse failure after retry
                state.error_flags.append({
                    "agent": self.name,
                    "ticker": ticker,
                    "round": round_num,
                    "error": "Judge JSON parse failure after retry",
                })
                break

            debate_history.append({
                "round": round_num,
                "bull": bull_arg,
                "bear": bear_arg,
            })
            last_verdict = verdict

            # --- Early termination ---
            direction = verdict.get("direction", "")
            confidence = verdict.get("confidence", 0.0)

            if direction == prev_direction and confidence > 0.85:
                consecutive_same += 1
            else:
                consecutive_same = 1
                prev_direction = direction

            if consecutive_same >= 2:
                logger.info(
                    "Debate early stop for %s at round %d (confidence=%.2f)",
                    ticker, round_num, confidence,
                )
                break

        if last_verdict is None:
            return None, total_tokens

        return last_verdict, total_tokens

    # ------------------------------------------------------------------
    # LLM call helpers
    # ------------------------------------------------------------------

    async def _call_bull(
        self,
        ticker: str,
        factor_scores: list[dict[str, Any]],
        debate_history: list[dict[str, Any]],
    ) -> tuple[str, int]:
        """Render bull prompt and call LLM. Returns (argument, tokens_used)."""
        prev = self._previous_rounds(debate_history)
        template = self._jinja.get_template("debate_bull.j2")
        prompt = template.render(
            ticker=ticker,
            factor_scores=factor_scores,
            smart_money_context="",
            fund_flow_context="",
            bull_previous=prev.get("bull"),
            bear_previous=prev.get("bear"),
            judge_previous=prev.get("judge"),
        )
        resp = await self.llm.chat(
            model=settings.LLM_MODEL_PRIMARY,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return resp["content"], resp.get("usage", {}).get("total_tokens", 0)

    async def _call_bear(
        self,
        ticker: str,
        factor_scores: list[dict[str, Any]],
        debate_history: list[dict[str, Any]],
    ) -> tuple[str, int]:
        """Render bear prompt and call LLM. Returns (argument, tokens_used)."""
        prev = self._previous_rounds(debate_history)
        template = self._jinja.get_template("debate_bear.j2")
        prompt = template.render(
            ticker=ticker,
            factor_scores=factor_scores,
            smart_money_context="",
            fund_flow_context="",
            bull_previous=prev.get("bull"),
            bear_previous=prev.get("bear"),
            judge_previous=prev.get("judge"),
        )
        resp = await self.llm.chat(
            model=settings.LLM_MODEL_PRIMARY,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return resp["content"], resp.get("usage", {}).get("total_tokens", 0)

    async def _call_judge(
        self,
        ticker: str,
        factor_scores: list[dict[str, Any]],
        debate_history: list[dict[str, Any]],
        bull_arg: str,
        bear_arg: str,
        round_num: int,
    ) -> tuple[dict[str, Any] | None, int]:
        """Render judge prompt, call LLM, parse JSON. Retry once on failure."""
        current_round = {
            "round": round_num,
            "bull": bull_arg,
            "bear": bear_arg,
        }
        all_history = debate_history + [current_round]

        template = self._jinja.get_template("debate_judge.j2")
        prompt = template.render(
            ticker=ticker,
            factor_scores=factor_scores,
            debate_history=all_history,
        )

        total_tokens = 0
        for attempt in range(2):
            resp = await self.llm.chat(
                model=settings.LLM_MODEL_MINI,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            total_tokens += resp.get("usage", {}).get("total_tokens", 0)
            content = resp["content"]

            parsed = self._parse_judge_json(content)
            if parsed is not None:
                return parsed, total_tokens

            logger.warning(
                "Judge JSON parse failed for %s round %d attempt %d",
                ticker, round_num, attempt + 1,
            )

        return None, total_tokens

    # ------------------------------------------------------------------
    # Pure helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_factor_scores(
        ticker: str, state: PipelineState
    ) -> list[dict[str, Any]]:
        """Extract factor_scores from analyst_outputs for a ticker."""
        outputs = state.analyst_outputs.get(ticker, {})
        scores: list[dict[str, Any]] = outputs.get("factor_scores", [])
        if not scores:
            logger.warning("No factor_scores found for ticker=%s", ticker)
        return scores

    @staticmethod
    def _previous_rounds(
        debate_history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract the most recent round's bull/bear/judge from history."""
        if not debate_history:
            return {}
        last = debate_history[-1]
        return {
            "bull": last.get("bull", ""),
            "bear": last.get("bear", ""),
            "judge": last.get("judge"),
        }

    @staticmethod
    def _parse_judge_json(content: str) -> dict[str, Any] | None:
        """Parse Judge JSON response. Returns None on failure."""
        if not content:
            return None
        content = content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        try:
            data: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError:
            return None
        # Validate required fields
        required = {"direction", "confidence", "rationale", "rounds_used"}
        if not required.issubset(data.keys()):
            return None
        if data["direction"] not in ("bullish", "bearish", "neutral"):
            return None
        if not isinstance(data["confidence"], (int, float)):
            return None
        if not (0.0 <= data["confidence"] <= 1.0):
            return None
        return data
