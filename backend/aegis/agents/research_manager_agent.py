"""Research Manager Agent — Recommendation ranking and synthesis with LLM.

Input: state.options_step2, state.debate_results, state.positions
Output: state.recommendations (sorted), state.pending_triggers (placeholder)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from jinja2 import Environment, FileSystemLoader

from aegis.agents.base import BaseAgent
from aegis.llm.client import LLMClient
from aegis.pipeline.state import PipelineState, Recommendation
from aegis.registry.agent_registry import AgentManifest

PROMPTS_DIR = Path(__file__).parent.parent.parent / "config" / "prompts"

URGENCY_WEIGHT: dict[str, int] = {"high": 3, "medium": 2, "low": 1}


class ResearchManagerAgent(BaseAgent):
    """Synthesize and rank final recommendations using LLM.

    Reads Options S2 proposals, debate results, and portfolio state.
    Calls LLM (gpt-4o) to generate ranked recommendations, then sorts
    by urgency × score. Writes pending_triggers = [] as M1 placeholder.
    """

    name = "research_manager"
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="research_manager",
        version="0.1.0",
        requires=["options_step2", "debate_results", "positions"],
        provides=["recommendations", "pending_triggers", "extensions.research_manager"],
        tags=["research", "ranking", "synthesis"],
        llm_dependency=True,
        parallel_group=None,
        pipeline_mode="full",
    )

    def __init__(self, memory: Any, tools: dict[str, Any], config: dict[str, Any]):
        super().__init__(memory, tools, config)
        self._llm = LLMClient()
        self._jinja = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))

    async def run(self, state: PipelineState) -> PipelineState:
        try:
            await self._synthesize(state)
        except Exception as e:
            state.error_flags.append({
                "agent": self.name,
                "error": str(e),
            })

        # M1 placeholder: pending_triggers not implemented yet
        state.pending_triggers = []

        return state

    async def _synthesize(self, state: PipelineState) -> None:
        ticker = state.tickers[0] if state.tickers else "QQQ"

        # Build portfolio summary
        positions = state.positions
        portfolio = {
            "total_nav": positions.get("total_nav", 100000.0),
            "cash": positions.get("cash", 50000.0),
            "positions": positions.get("holdings", []),
        }

        # Render prompt
        template = self._jinja.get_template("research_manager_synthesis.j2")
        prompt = template.render(
            ticker=ticker,
            options_step2=state.options_step2,
            debate_results=state.debate_results,
            portfolio=portfolio,
        )

        # Call LLM
        response = await self._llm.chat(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        # Parse response
        try:
            result = json.loads(response["content"])
        except (json.JSONDecodeError, KeyError):
            state.error_flags.append({
                "agent": self.name,
                "error": "Failed to parse LLM JSON response",
            })
            return

        raw_recs = result.get("recommendations", [])

        # Build Recommendation objects
        recommendations: list[Recommendation] = []
        for r in raw_recs:
            rec = Recommendation(
                ticker=r.get("ticker", ticker),
                action=r.get("action", "hold"),
                strategy=r.get("strategy", "stock"),
                rationale=r.get("rationale", ""),
                urgency=r.get("urgency", "medium"),
                score=float(r.get("score", 50)),
                delta_dollars_delta=float(r.get("delta_dollars_delta", 0)),
            )
            recommendations.append(rec)

        # Sort by urgency × score
        recommendations = self._sort_recommendations(recommendations)
        state.recommendations = recommendations

        self.write_extension(state, "synthesis_raw", {
            "total_recommendations": len(recommendations),
            "llm_model": response.get("model", "unknown"),
        })

    @staticmethod
    def _sort_recommendations(recs: list[Recommendation]) -> list[Recommendation]:
        return sorted(
            recs,
            key=lambda r: URGENCY_WEIGHT.get(r.urgency, 2) * r.score,
            reverse=True,
        )
