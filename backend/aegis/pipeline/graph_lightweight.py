"""Lightweight Pipeline StateGraph — 4-node subgraph, zero LLM calls.

START → DataHarvester(lightweight) → Trend/Phase → Level → health_check → END

health_check is a pure calculation node (no Agent, no LLM).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph
from loguru import logger

from aegis.agents.data_harvester_agent import DataHarvesterAgent
from aegis.agents.level_analyst_agent import LevelAnalystAgent
from aegis.agents.trend_phase_analyst_agent import TrendPhaseAnalystAgent
from aegis.pipeline.state import PipelineState

_LW_AGENT_CLASSES: dict[str, type] = {
    "data_harvester": DataHarvesterAgent,
    "trend_phase_analyst": TrendPhaseAnalystAgent,
    "level_analyst": LevelAnalystAgent,
}


def _run_lw_agent(agent_name: str) -> Callable[[PipelineState], Any]:
    """Return a LangGraph node function for lightweight agents (no LLM)."""

    async def node_fn(state: PipelineState) -> dict[str, Any]:
        agent_cls = _LW_AGENT_CLASSES[agent_name]
        agent = agent_cls(memory={}, tools={}, config={})
        t0 = time.monotonic()
        try:
            result = await agent.run(state)
        except Exception as exc:
            logger.exception(f"[{agent_name}] lightweight failed: {exc}")
            state.error_flags.append({"agent": agent_name, "error": str(exc)})
            result = state
        elapsed = time.monotonic() - t0
        result.agent_timings[agent_name] = elapsed
        return result.model_dump()  # type: ignore[no-any-return]

    return node_fn


async def _lightweight_health_check(state: PipelineState) -> dict[str, Any]:
    """Pure calculation node: check price deviation for passive holdings.

    No Agent, no LLM, no external IO. Computes health_scores and
    passive_health_alerts from market_data vs positions.
    """
    alerts: list[dict[str, Any]] = []
    scores: dict[str, float] = {}

    tickers = state.tickers_holdings_passive or state.tickers
    if not tickers:
        return {
            "passive_health_alerts": alerts,
            "health_scores": scores,
        }

    positions = state.positions.get("holdings", [])
    for ticker in tickers:
        price = state.market_data.get(ticker, {}).get("price", 0)
        if price <= 0:
            scores[ticker] = 100.0
            continue

        avg_cost = price  # default: no position → assume at market
        for pos in positions:
            if pos.get("ticker") == ticker:
                avg_cost = pos.get("avg_cost", price)
                break

        if avg_cost > 0:
            pct_change = (price - avg_cost) / avg_cost
            score = 100.0 - abs(pct_change) * 100
            scores[ticker] = max(0.0, min(100.0, score))
            if abs(pct_change) > 0.10:
                alerts.append(
                    {
                        "ticker": ticker,
                        "type": "price_deviation",
                        "pct_change": round(pct_change, 4),
                        "severity": "warning",
                    }
                )
        else:
            scores[ticker] = 100.0

    return {
        "passive_health_alerts": alerts,
        "health_scores": scores,
    }


def build_lightweight_graph() -> StateGraph:  # type: ignore[type-arg]
    """Build the Lightweight Pipeline StateGraph (zero LLM)."""
    graph = StateGraph(PipelineState)

    graph.add_node("data_harvester", _run_lw_agent("data_harvester"))  # type: ignore[call-overload]
    graph.add_node("trend_phase", _run_lw_agent("trend_phase_analyst"))  # type: ignore[call-overload]
    graph.add_node("level", _run_lw_agent("level_analyst"))  # type: ignore[call-overload]
    graph.add_node("health_check", _lightweight_health_check)

    graph.set_entry_point("data_harvester")
    graph.add_edge("data_harvester", "trend_phase")
    graph.add_edge("trend_phase", "level")
    graph.add_edge("level", "health_check")
    graph.add_edge("health_check", END)

    return graph
