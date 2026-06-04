"""Pipeline runner — entry points for Full and Lightweight pipelines."""

from __future__ import annotations

import time
import uuid

from aegis.pipeline.state import PipelineMode, PipelineState


async def run_full(ticker: str, mode: PipelineMode = "manual") -> PipelineState:
    """Execute the Full Pipeline for a single ticker.

    Args:
        ticker: Ticker symbol to analyze (e.g. "QQQ").
        mode: Pipeline mode — "pre-market", "post-market", or "manual".

    Returns:
        Final PipelineState with all agent outputs, timings, and recommendations.
    """
    from aegis.pipeline.graph_full import build_full_graph  # lazy — avoids broken import chain

    state = PipelineState(
        pipeline_id=str(uuid.uuid4())[:8],
        mode=mode,
        tickers=[ticker],
        pipeline_mode="full",
    )
    graph = build_full_graph()
    app = graph.compile()
    t0 = time.monotonic()
    result = await app.ainvoke(state)
    elapsed = time.monotonic() - t0
    final = PipelineState(**result)
    final.agent_timings["_total"] = elapsed
    return final


async def run_lightweight(tickers_passive: list[str]) -> PipelineState:
    """Execute the Lightweight Pipeline for passive holdings.

    Zero LLM calls. Computes health scores and price deviation alerts.

    Args:
        tickers_passive: List of passive holding tickers to check.

    Returns:
        Final PipelineState with health_scores and passive_health_alerts.
    """
    from aegis.pipeline.graph_lightweight import (  # lazy — avoids broken import chain
        build_lightweight_graph,
    )

    if not tickers_passive:
        return PipelineState(
            pipeline_id=str(uuid.uuid4())[:8],
            mode="manual",
            pipeline_mode="lightweight",
        )

    state = PipelineState(
        pipeline_id=str(uuid.uuid4())[:8],
        mode="manual",
        tickers=tickers_passive,
        pipeline_mode="lightweight",
        tickers_holdings_passive=tickers_passive,
    )
    graph = build_lightweight_graph()
    app = graph.compile()
    t0 = time.monotonic()
    result = await app.ainvoke(state)
    elapsed = time.monotonic() - t0
    final = PipelineState(**result)
    final.agent_timings["_total"] = elapsed
    return final
