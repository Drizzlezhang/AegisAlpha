"""Pipeline runner — entry points for Full and Lightweight pipelines."""

from __future__ import annotations

import contextlib
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aegis.memory.long_term_store import LongTermStore
from aegis.memory.short_term_store import ShortTermStore
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


async def _post_recommendation_hook(state: PipelineState) -> None:
    """Auto-create ThesisCards for buy recommendations that pass Risk Gate.

    Only creates ThesisCards for buy/add actions. Skips hold/close/sell.
    Must not block Pipeline — all failures are logged and swallowed.
    """
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from aegis.memory.long_term_store import LongTermStore
        from aegis.memory.service import MemoryService
        from aegis.memory.short_term_store import ShortTermStore
        from aegis.memory.thesis_store import ThesisStore as MemoryThesisStore
        from aegis.memory.vector_store import VectorStore
        from aegis.memory.weight_adapter import WeightAdapter
        from aegis.memory.weight_store import WeightStore
        from aegis.services.thesis_service import ThesisService
        from aegis.storage.thesis_store import ThesisStore

        engine = create_engine(settings.DATABASE_URL)

        def sync_session_factory() -> Session:
            return Session(engine)

        async_engine = create_async_engine(
            settings.DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///"),
            echo=False,
        )

        def async_session_factory() -> AsyncSession:
            return AsyncSession(async_engine)

        thesis_store = ThesisStore(async_session_factory)
        short_term = ShortTermStore(sync_session_factory)
        long_term = LongTermStore(sync_session_factory)
        vector = VectorStore()
        memory = MemoryService(short_term, long_term, vector)
        weight_store = WeightStore()
        memory_thesis_store = MemoryThesisStore()
        weight_adapter = WeightAdapter(weight_store, memory_thesis_store)

        thesis_service = ThesisService(
            thesis_store=thesis_store,
            memory=memory,
            weight_adapter=weight_adapter,
            long_term_store=long_term,
            session_factory=sync_session_factory,
        )

        created_count = 0
        for rec in state.recommendations:
            if rec.action not in ("buy", "add"):
                continue

            ticker = rec.ticker

            # Skip if active thesis already exists
            if await thesis_service.has_active_thesis(ticker):
                logger.debug(f"Thesis hook: skipping {ticker} — active thesis exists")
                continue

            # Derive direction from strategy
            if rec.strategy == "covered_call":
                direction = "cc"
            else:
                direction = "long"

            # Derive entry_price from market_data
            market = state.market_data.get(ticker, {})
            entry_price = float(market.get("price", market.get("close", 0)))

            # Derive target_price and stop_price from analyst_outputs
            levels = state.analyst_outputs.get("levels", {}).get(ticker, {})
            target_price = None
            stop_price = None

            resistance_levels = levels.get("resistance_levels", [])
            if resistance_levels:
                target_price = float(resistance_levels[0])

            support_levels = levels.get("support_levels", [])
            if support_levels:
                stop_price = float(support_levels[0])

            # Override with recommendation-specific stop_loss if available
            if rec.stop_loss:
                stop_price = float(rec.stop_loss.get("trigger_price", stop_price or 0))

            # Build key_assumptions from rationale + debate
            key_assumptions = [rec.rationale] if rec.rationale else []
            debate = state.debate_results.get(ticker, {})
            if debate:
                direction_label = debate.get("direction", "")
                confidence = debate.get("confidence", 0)
                key_assumptions.append(
                    f"Debate: {direction_label} (confidence={confidence:.0%})"
                )

            # Build recommendation dict for ThesisService
            recommendation = {
                "ticker": ticker,
                "direction": direction,
                "entry_mode": state.entry_mode.get(ticker, "active_right"),
                "entry_price": entry_price,
                "target_price": target_price,
                "stop_price": stop_price,
                "key_assumptions": key_assumptions,
            }

            try:
                thesis_id = await thesis_service.create_from_recommendation(
                    recommendation=recommendation,
                    weight_snapshot=state.weight_snapshot,
                    user_confirmed=True,
                )
                logger.info(
                    f"Thesis hook: created thesis {thesis_id} for {ticker} "
                    f"({direction}, {rec.strategy})"
                )
                created_count += 1
            except ValueError as e:
                logger.warning(f"Thesis hook: skipped {ticker} — {e}")
            except Exception:
                logger.exception(f"Thesis hook: failed to create thesis for {ticker}")

        if created_count > 0:
            logger.info(f"Thesis hook: created {created_count} thesis cards")

    except Exception:
        logger.exception("Thesis hook failed (non-blocking)")


async def _post_pipeline_archive(state: PipelineState) -> None:
    """Archive pipeline outputs to Memory. Must not block Pipeline.

    Archives:
        - scratchpad → short-term (TTL 7 days)
        - debate_results → long-term (data_type="debate")
        - recommendations → long-term (data_type="recommendation")
        - smart_money_data → long-term (data_type="smart_money_flow")
        - fund_flow_data → long-term (data_type="fund_flow")
    """
    try:
        engine = create_engine(settings.DATABASE_URL)
        with Session(engine) as session:
            short_term = ShortTermStore(lambda: session)
            long_term = LongTermStore(lambda: session)

            # 1. Archive scratchpad → short-term (TTL 7 days)
            if state.scratchpad:
                for agent_name, trace in state.scratchpad.items():
                    short_term.insert(
                        {
                            "ticker": state.tickers[0] if state.tickers else "",
                            "data_type": f"scratchpad/{agent_name}",
                            "content": {"trace": trace},
                            "pipeline_id": state.pipeline_id,
                        },
                        ttl_days=7,
                    )

            # 2. Archive debate_results → long-term
            if state.debate_results:
                for ticker, result in state.debate_results.items():
                    long_term.insert(
                        {
                            "ticker": ticker,
                            "data_type": "debate",
                            "content": result,
                            "original_date": datetime.now(UTC),
                        }
                    )

            # 3. Archive recommendations → long-term
            for rec in state.recommendations:
                long_term.insert(
                    {
                        "ticker": rec.ticker,
                        "data_type": "recommendation",
                        "content": rec.model_dump(),
                        "original_date": datetime.now(UTC),
                    }
                )

            # 4. Archive smart_money_data → long-term
            if state.smart_money_data:
                for ticker, data in state.smart_money_data.items():
                    long_term.insert(
                        {
                            "ticker": ticker,
                            "data_type": "smart_money_flow",
                            "content": data,
                            "original_date": datetime.now(UTC),
                        }
                    )

            # 5. Archive fund_flow_data → long-term
            if state.fund_flow_data:
                for ticker, data in state.fund_flow_data.items():
                    long_term.insert(
                        {
                            "ticker": ticker,
                            "data_type": "fund_flow",
                            "content": data,
                            "original_date": datetime.now(UTC),
                        }
                    )
    except Exception:
        logger.exception("Pipeline archive failed (non-blocking)")


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

    # Archive pipeline outputs to Memory (non-blocking)
    await _post_pipeline_archive(final)

    # Auto-create ThesisCards for buy recommendations (non-blocking)
    await _post_recommendation_hook(final)

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

    # Archive pipeline outputs to Memory (non-blocking)
    await _post_pipeline_archive(final)

    return final
