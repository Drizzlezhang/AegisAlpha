"""Smart Money Agent — institutional options flow analysis with LLM narrative.

Input: state.tickers, state.market_data
Output: state.smart_money_data[ticker] with score/direction/unusual_options/oi_changes/narrative
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from aegis.agents.base import BaseAgent
from aegis.llm.client import LLMClient
from aegis.pipeline.state import PipelineState
from aegis.registry.agent_registry import AgentManifest
from aegis.tools.base import ToolResult
from aegis.utils.settings import settings


class SmartMoneyAgent(BaseAgent):
    """Analyzes institutional options flow to compute smart money score and narrative."""

    name = "smart_money_agent"
    manifest = AgentManifest(
        name="smart_money_agent",
        version="0.1.0",
        requires=["tickers", "market_data"],
        provides=["smart_money_data"],
        tags=["smart_money", "options_flow", "signal"],
        llm_dependency=True,
        parallel_group="signal_analysts",
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

    async def run(self, state: PipelineState) -> PipelineState:
        start_time = time.monotonic()

        for ticker in state.tickers:
            try:
                unusual_options = await self._fetch_unusual_options(ticker)
                oi_changes = await self._fetch_oi_changes(ticker)

                score, direction_bias = self._compute_score(unusual_options, oi_changes)

                narrative = await self._generate_narrative(
                    ticker, score, direction_bias, unusual_options, oi_changes
                )

                state.smart_money_data[ticker] = {
                    "smart_money_score": score,
                    "direction_bias": direction_bias,
                    "unusual_options": unusual_options[:5],
                    "oi_changes": oi_changes,
                    "narrative": narrative,
                }

                logger.info(
                    "SmartMoneyAgent: %s score=%.1f direction=%s options=%d",
                    ticker,
                    score,
                    direction_bias,
                    len(unusual_options),
                )

            except Exception:
                logger.exception("SmartMoneyAgent failed for ticker=%s", ticker)
                state.error_flags.append(
                    {
                        "agent": self.name,
                        "ticker": ticker,
                        "error": "SmartMoneyAgent unhandled exception",
                    }
                )

        elapsed = time.monotonic() - start_time
        state.agent_timings[self.name] = elapsed
        self.write_extension(state, "raw_data", dict(state.smart_money_data))
        return state

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def _fetch_unusual_options(self, ticker: str) -> list[dict[str, Any]]:
        """Fetch unusual options from UW, fallback to MarketChameleon."""
        uw_tool = self.tools.get("unusual_whales")
        if uw_tool is not None:
            result: ToolResult = await uw_tool.fetch(ticker=ticker)
            if result.success and isinstance(result.data, list):
                return result.data

        # Fallback to MarketChameleon
        mc_tool = self.tools.get("market_chameleon")
        if mc_tool is not None:
            logger.info("SmartMoneyAgent: falling back to market_chameleon for %s", ticker)
            result = await mc_tool.fetch(ticker=ticker)
            if result.success and isinstance(result.data, list):
                return result.data

        logger.warning("SmartMoneyAgent: no unusual options data for %s", ticker)
        return []

    async def _fetch_oi_changes(self, ticker: str) -> dict[str, Any]:
        """Fetch OI changes from OIChangeAdapter."""
        oi_tool = self.tools.get("oi_change")
        if oi_tool is None:
            return {
                "ticker": ticker,
                "call_oi_delta": 0,
                "put_oi_delta": 0,
                "oi_delta": 0,
                "daily_oi": [],
            }

        result: ToolResult = await oi_tool.fetch(ticker=ticker)
        if result.success and isinstance(result.data, dict):
            return result.data

        logger.warning("SmartMoneyAgent: no OI data for %s", ticker)
        return {
            "ticker": ticker,
            "call_oi_delta": 0,
            "put_oi_delta": 0,
            "oi_delta": 0,
            "daily_oi": [],
        }

    # ------------------------------------------------------------------
    # Score computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_score(
        unusual_options: list[dict[str, Any]],
        oi_changes: dict[str, Any],
    ) -> tuple[float, str]:
        """Compute smart money score (0-100) and direction bias.

        Algorithm:
          - direction_score (0-40): abs(call_ratio - 0.5) * 80
          - premium_score (0-30): abs(premium_bias - 0.5) * 60
          - oi_score (0-30): min(abs(oi_delta) * 3, 30)
          - Normalize each sub-score to 0-1, then weight to 0-100:
            total = (0.35 * direction_norm + 0.35 * premium_norm + 0.30 * oi_norm) * 100
        """
        # 1. Direction consistency (0-40)
        call_count = sum(1 for o in unusual_options if o.get("type") == "call")
        put_count = sum(1 for o in unusual_options if o.get("type") == "put")
        total = call_count + put_count

        if total > 0:
            call_ratio = call_count / total
            direction_score = abs(call_ratio - 0.5) * 80
        else:
            call_ratio = 0.5
            direction_score = 0.0

        # 2. Premium-weighted bias (0-30)
        total_premium = sum(o.get("premium", 0) for o in unusual_options)
        call_premium = sum(
            o.get("premium", 0) for o in unusual_options if o.get("type") == "call"
        )
        if total_premium > 0:
            premium_bias = call_premium / total_premium
            premium_score = abs(premium_bias - 0.5) * 60
        else:
            premium_score = 0.0

        # 3. OI change trend (0-30)
        oi_delta = oi_changes.get("oi_delta", 0)
        oi_score = min(abs(oi_delta) * 3, 30)

        # Normalize each sub-score to 0-1, then weight to 0-100
        direction_norm = direction_score / 40.0 if direction_score > 0 else 0.0
        premium_norm = premium_score / 30.0 if premium_score > 0 else 0.0
        oi_norm = oi_score / 30.0 if oi_score > 0 else 0.0

        total_score = (0.35 * direction_norm + 0.35 * premium_norm + 0.30 * oi_norm) * 100

        # Direction bias
        if call_ratio > 0.55:
            direction_bias = "bullish"
        elif call_ratio < 0.45:
            direction_bias = "bearish"
        else:
            direction_bias = "neutral"

        return round(total_score, 2), direction_bias

    # ------------------------------------------------------------------
    # LLM narrative
    # ------------------------------------------------------------------

    async def _generate_narrative(
        self,
        ticker: str,
        score: float,
        direction_bias: str,
        unusual_options: list[dict[str, Any]],
        oi_changes: dict[str, Any],
    ) -> str:
        """Generate 1-2 sentence narrative via LLM. Returns empty string on failure."""
        try:
            template = self._jinja.get_template("smart_money_narrative.j2")
            prompt = template.render(
                ticker=ticker,
                smart_money_score=score,
                direction_bias=direction_bias,
                unusual_options=unusual_options,
                oi_changes=oi_changes,
            )
            resp = await self.llm.chat(
                model=settings.LLM_MODEL_MINI,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
            return str(resp["content"]).strip()
        except Exception:
            logger.exception("SmartMoneyAgent narrative generation failed for %s", ticker)
            return ""
