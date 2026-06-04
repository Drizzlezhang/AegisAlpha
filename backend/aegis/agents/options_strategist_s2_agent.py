"""Options Strategist Step 2 Agent — Final contract proposal generation with LLM.

Input: state.options_step1, state.debate_results, state.analyst_outputs.levels
Output: state.options_step2[ticker] with contracts, stop_loss, delta_dollars_delta
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from jinja2 import Environment, FileSystemLoader

from aegis.agents.base import BaseAgent
from aegis.calculators.stop_loss import compute_stop_loss
from aegis.llm.client import LLMClient
from aegis.pipeline.state import PipelineState
from aegis.registry.agent_registry import AgentManifest

PROMPTS_DIR = Path(__file__).parent.parent.parent / "config" / "prompts"


class OptionsStrategistS2Agent(BaseAgent):
    """Generate final option contract proposals using LLM.

    Reads S1 candidates, debate results, and support/resistance levels.
    Calls LLM (gpt-4o) to select best contracts, then computes stop_loss
    for each contract (support_based if levels available, else fixed_pct).
    """

    name = "options_strategist_s2"
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="options_strategist_s2",
        version="0.1.0",
        requires=["options_step1", "debate_results", "analyst_outputs.levels"],
        provides=["options_step2", "extensions.options_strategist_s2"],
        tags=["options", "strategy", "signal"],
        llm_dependency=True,
        parallel_group=None,
        pipeline_mode="full",
    )

    def __init__(self, memory: Any, tools: dict[str, Any], config: dict[str, Any]):
        super().__init__(memory, tools, config)
        self._llm = LLMClient()
        self._jinja = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))

    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            try:
                await self._process_ticker(state, ticker)
            except Exception as e:
                state.error_flags.append(
                    {
                        "agent": self.name,
                        "ticker": ticker,
                        "error": str(e),
                    }
                )
        return state

    async def _process_ticker(self, state: PipelineState, ticker: str) -> None:
        # Read inputs
        s1_data = state.options_step1.get(ticker, {})
        candidates = s1_data.get("candidates", [])
        if not candidates:
            state.options_step2[ticker] = {}
            return

        debate = state.debate_results.get(ticker, {})
        levels = state.analyst_outputs.get("levels", {}).get(ticker, {})

        # Build and render prompt
        template = self._jinja.get_template("options_strategist_s2.j2")
        prompt = template.render(
            ticker=ticker,
            candidates=candidates,
            debate=debate,
            levels=levels,
        )

        # Call LLM
        response = await self._llm.chat(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        # Parse response
        try:
            result = json.loads(response["content"])
        except (json.JSONDecodeError, KeyError):
            state.error_flags.append(
                {
                    "agent": self.name,
                    "ticker": ticker,
                    "error": "Failed to parse LLM JSON response",
                }
            )
            state.options_step2[ticker] = {}
            return

        contracts = result.get("contracts", [])

        # Compute stop_loss for each contract
        support_levels = levels.get("support_levels", [])
        for c in contracts:
            entry_price = c.get("entry_price", 0.0)
            if support_levels:
                stop = compute_stop_loss(
                    entry_price, "support_based", support_level=support_levels[0]
                )
            else:
                stop = compute_stop_loss(entry_price, "fixed_pct")
            c["stop_loss"] = stop.model_dump()
            c["delta_dollars_delta"] = c.get("delta_dollars_delta", 0.0)

        state.options_step2[ticker] = {
            "contracts": contracts,
        }

        self.write_extension(
            state,
            "s2_raw",
            {
                "ticker": ticker,
                "contracts_count": len(contracts),
                "stop_loss_mode": "support_based" if support_levels else "fixed_pct",
            },
        )
