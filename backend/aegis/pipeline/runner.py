"""Pipeline runner — entry points for Full and Lightweight pipelines."""

from __future__ import annotations

import contextlib
import time
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aegis.memory.weight_store import WeightStore
from aegis.pipeline.state import PipelineMode, PipelineState
from aegis.utils.settings import settings


def _inject_weight_snapshot() -> dict[str, dict[str, Any]]:
    """Load current factor weights from DB and return as weight_snapshot dict.

    Returns empty dict on failure — must not block Pipeline.
    """
    try:
        engine = create_engine(settings.DATABASE_URL)
        with Session(engine) as session:
            store = WeightStore()
            return store.get_all_weights(session)
    except Exception:
        logger.exception("Failed to inject weight_snapshot, using empty dict")
        return {}


async def run_full(
    ticker: str,
    mode: PipelineMode = "manual",
    ws_manager: Any = None,
) -> PipelineState:
    """Execute the Full Pipeline for a single ticker.

    Args:
        ticker: Ticker symbol to analyze (e.g. "QQQ").
        mode: Pipeline mode — "pre-market", "post-market", or "manual".
        ws_manager: Optional PipelineWSManager for WebSocket event broadcasting.

    Returns:
        Final PipelineState with all agent outputs, timings, and recommendations.
    """
    from aegis.pipeline.graph_builder import GraphBuilder

    state = PipelineState(
        pipeline_id=str(uuid.uuid4())[:8],
        mode=mode,
        tickers=[ticker],
        pipeline_mode="full",
    )

    # Inject current factor weights into state before graph execution
    state.weight_snapshot = _inject_weight_snapshot()

    builder = GraphBuilder(ws_manager=ws_manager)
    app = builder.build("full")
    t0 = time.monotonic()
    result = await app.ainvoke(state)
    elapsed = time.monotonic() - t0
    final = PipelineState(**result)
    final.agent_timings["_total"] = elapsed

    # Emit pipeline_complete
    if ws_manager:
        with contextlib.suppress(Exception):
            await ws_manager.emit_pipeline_complete(
                final.pipeline_id,
                {
                    "total_elapsed": elapsed,
                    "recommendations": len(final.recommendations),
                    "blocked": len(final.blocked_recommendations),
                    "errors": len(final.error_flags),
                },
            )

    return final


async def run_lightweight(
    tickers_passive: list[str],
    ws_manager: Any = None,
) -> PipelineState:
    """Execute the Lightweight Pipeline for passive holdings.

    Zero LLM calls. Computes health scores and price deviation alerts.

    Args:
        tickers_passive: List of passive holding tickers to check.
        ws_manager: Optional PipelineWSManager for WebSocket event broadcasting.

    Returns:
        Final PipelineState with health_scores and passive_health_alerts.
    """
    from aegis.pipeline.graph_builder import GraphBuilder

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
    builder = GraphBuilder(ws_manager=ws_manager)
    app = builder.build("lightweight")
    t0 = time.monotonic()
    result = await app.ainvoke(state)
    elapsed = time.monotonic() - t0
    final = PipelineState(**result)
    final.agent_timings["_total"] = elapsed

    # Emit pipeline_complete
    if ws_manager:
        with contextlib.suppress(Exception):
            await ws_manager.emit_pipeline_complete(
                final.pipeline_id,
                {
                    "total_elapsed": elapsed,
                    "health_scores": final.health_scores,
                    "alerts": len(final.passive_health_alerts),
                },
            )

    return final
