"""Full Pipeline StateGraph — manifest-driven assembly via GraphBuilder.

START → DataHarvester → PortfolioOrchestrator
  → [parallel] TrendPhase / Level / OptionsS1 / SmartMoney / FundFlow
  → [fan-in] Debate → OptionsS2 → ResearchManager → RiskGate → END

M2 Branch E+F: uses GraphBuilder with parallel fan-out/fan-in for signal layer.
"""

from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from aegis.pipeline.graph_builder import GraphBuilder
from aegis.pipeline.state import PipelineState


def build_full_graph() -> CompiledStateGraph[PipelineState, None, PipelineState, PipelineState]:
    """Build the Full Pipeline using manifest-driven GraphBuilder.

    Signal layer agents (parallel_group: signal_analysts) execute in parallel
    via LangGraph Send-based fan-out/fan-in. Annotated state reducers handle
    conflict-free parallel writes.
    """
    builder = GraphBuilder()
    return builder.build("full")
