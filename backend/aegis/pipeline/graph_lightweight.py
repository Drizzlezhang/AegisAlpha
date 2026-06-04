"""Lightweight Pipeline StateGraph — manifest-driven assembly via GraphBuilder.

START → DataHarvester → PortfolioOrchestrator
  → [parallel] TrendPhase / Level
  → [fan-in] PassiveHealthCheck → END

M2 Branch E+F: uses GraphBuilder with PassiveHealthCheckAgent for
dynamic stop loss, DTE warning, theta acceleration, and price deviation checks.
Zero LLM calls.
"""

from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from aegis.pipeline.graph_builder import GraphBuilder
from aegis.pipeline.state import PipelineState


def build_lightweight_graph() -> CompiledStateGraph[PipelineState, None, PipelineState, PipelineState]:
    """Build the Lightweight Pipeline using manifest-driven GraphBuilder.

    Only rule-only agents (llm_dependency=False) are included.
    PassiveHealthCheckAgent handles stop loss, DTE, theta, and deviation checks.
    """
    builder = GraphBuilder()
    return builder.build("lightweight")
