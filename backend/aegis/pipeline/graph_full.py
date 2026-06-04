"""Full Pipeline StateGraph — 9-node manual assembly.

START → DataHarvester → PortfolioOrchestrator → Trend/Phase → Level
  → Options S1 → Debate → Options S2 → Research Manager → Risk Gate → END

M1: fully sequential (parallel fan-out requires Annotated state reducers — M2+).
M2+: migrate to registry.graph_builder with proper parallel group support.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph
from loguru import logger

from aegis.agents.data_harvester_agent import DataHarvesterAgent
from aegis.agents.debate_agent import DebateAgent
from aegis.agents.level_analyst_agent import LevelAnalystAgent
from aegis.agents.options_strategist_s1_agent import OptionsStrategistS1Agent
from aegis.agents.options_strategist_s2_agent import OptionsStrategistS2Agent
from aegis.agents.portfolio_orchestrator_agent import PortfolioOrchestratorAgent
from aegis.agents.research_manager_agent import ResearchManagerAgent
from aegis.agents.risk_gate_agent import RiskGateAgent
from aegis.agents.trend_phase_analyst_agent import TrendPhaseAnalystAgent
from aegis.pipeline.state import PipelineState

_AGENT_CLASSES: dict[str, type] = {
    "data_harvester": DataHarvesterAgent,
    "trend_phase_analyst": TrendPhaseAnalystAgent,
    "level_analyst": LevelAnalystAgent,
    "options_strategist_s1": OptionsStrategistS1Agent,
    "debate_agent": DebateAgent,
    "options_strategist_s2": OptionsStrategistS2Agent,
    "research_manager": ResearchManagerAgent,
    "portfolio_orchestrator": PortfolioOrchestratorAgent,
    "risk_gate": RiskGateAgent,
}


def _run_agent(agent_name: str) -> Callable[[PipelineState], Any]:
    """Return a LangGraph node function that instantiates and runs an agent.

    Each node:
    1. Instantiates the agent with empty DI (M1: agents don't use memory/tools yet)
    2. Calls agent.run(state)
    3. Catches exceptions → writes to state.error_flags
    4. Records elapsed time in state.agent_timings
    """

    async def node_fn(state: PipelineState) -> dict[str, Any]:
        agent_cls = _AGENT_CLASSES[agent_name]
        agent = agent_cls(memory={}, tools={}, config={})
        t0 = time.monotonic()
        try:
            result = await agent.run(state)
        except Exception as exc:
            logger.exception(f"[{agent_name}] failed: {exc}")
            state.error_flags.append({"agent": agent_name, "error": str(exc)})
            result = state
        elapsed = time.monotonic() - t0
        result.agent_timings[agent_name] = elapsed
        return result.model_dump()  # type: ignore[no-any-return]

    return node_fn


def build_full_graph() -> StateGraph:  # type: ignore[type-arg]
    """Build the Full Pipeline StateGraph with 9 agents."""
    graph = StateGraph(PipelineState)

    # Nodes
    graph.add_node("data_harvester", _run_agent("data_harvester"))  # type: ignore[arg-type]
    graph.add_node("trend_phase", _run_agent("trend_phase_analyst"))  # type: ignore[arg-type]
    graph.add_node("level", _run_agent("level_analyst"))  # type: ignore[arg-type]
    graph.add_node("options_s1", _run_agent("options_strategist_s1"))  # type: ignore[arg-type]
    graph.add_node("debate", _run_agent("debate_agent"))  # type: ignore[arg-type]
    graph.add_node("options_s2", _run_agent("options_strategist_s2"))  # type: ignore[arg-type]
    graph.add_node("research_manager", _run_agent("research_manager"))  # type: ignore[arg-type]
    graph.add_node("portfolio_orchestrator", _run_agent("portfolio_orchestrator"))  # type: ignore[arg-type]
    graph.add_node("risk_gate", _run_agent("risk_gate"))  # type: ignore[arg-type]

    # Edges — fully sequential (M1: parallel requires Annotated reducers)
    graph.set_entry_point("data_harvester")
    graph.add_edge("data_harvester", "portfolio_orchestrator")
    graph.add_edge("portfolio_orchestrator", "trend_phase")
    graph.add_edge("trend_phase", "level")
    graph.add_edge("level", "options_s1")
    graph.add_edge("options_s1", "debate")

    # Sequential chain
    graph.add_edge("debate", "options_s2")
    graph.add_edge("options_s2", "research_manager")
    graph.add_edge("research_manager", "risk_gate")
    graph.add_edge("risk_gate", END)

    return graph
