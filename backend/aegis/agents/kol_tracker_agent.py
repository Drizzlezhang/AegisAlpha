"""KOLTrackerAgent — social media signal collection and extraction.

Runs in signal_analysts parallel group. Collects posts from X/Twitter,
StockTwits, and Reddit via Tool Registry, then uses LLM (mini) to extract
structured trading signals.

Input: state.tickers, KOL sources from KOLStore
Output: state.kol_signals[ticker], state.extensions["kol_tracker"],
         kol_calls table records, Long-term Memory
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
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

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prompts"


class KOLTrackerAgent(BaseAgent):
    """Collects KOL signals from X, StockTwits, and Reddit.

    Flow:
      1. Get enabled KOL sources from KOLStore
      2. Group sources by platform
      3. Parallel fetch from 3 social tools
      4. LLM (mini) extracts structured signals
      5. Write to state.kol_signals + extensions + kol_calls + Long-term Memory
    """

    name = "kol_tracker"
    manifest = AgentManifest(
        name="kol_tracker",
        version="0.1.0",
        requires=["tickers"],
        provides=["kol_signals", "extensions.kol_tracker"],
        tags=["signal", "social"],
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
        self._jinja = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))

    async def run(self, state: PipelineState) -> PipelineState:
        start_time = time.monotonic()

        # Get KOLStore from config (injected by DI)
        kol_store = self.config.get("kol_store")
        if kol_store is None:
            logger.warning("KOLTrackerAgent: no KOLStore in config, skipping")
            state.agent_timings[self.name] = time.monotonic() - start_time
            return state

        # Get enabled KOL sources
        try:
            sources = await kol_store.list_sources(enabled_only=True)
        except Exception:
            logger.exception("KOLTrackerAgent: failed to list KOL sources")
            state.error_flags.append({
                "agent": self.name,
                "error": "Failed to list KOL sources",
            })
            state.agent_timings[self.name] = time.monotonic() - start_time
            return state

        if not sources:
            logger.info("KOLTrackerAgent: no enabled KOL sources, skipping")
            state.agent_timings[self.name] = time.monotonic() - start_time
            return state

        # Group sources by platform
        by_platform: dict[str, list[dict[str, Any]]] = {"x": [], "stocktwits": [], "reddit": []}
        for src in sources:
            platform = src.platform
            if platform in by_platform:
                by_platform[platform].append({
                    "id": src.id,
                    "name": src.name,
                    "handle": src.handle,
                    "reliability_score": src.reliability_score,
                })

        # Parallel fetch from 3 social tools
        tickers = state.tickers or []
        raw_posts: list[dict[str, Any]] = []

        # X/Twitter
        if by_platform["x"]:
            x_tool = self.tools.get("x_search")
            if x_tool:
                handles = [s["handle"] for s in by_platform["x"]]
                try:
                    result: ToolResult = await x_tool.fetch(
                        kol_handles=handles, tickers=tickers
                    )
                    if result.success and result.data:
                        raw_posts.extend(result.data)
                except Exception:
                    logger.exception("KOLTrackerAgent: x_search fetch failed")

        # StockTwits
        if by_platform["stocktwits"]:
            st_tool = self.tools.get("stocktwits_fetch")
            if st_tool:
                handles = [s["handle"] for s in by_platform["stocktwits"]]
                try:
                    st_result: ToolResult = await st_tool.fetch(
                        handles=handles, target_tickers=tickers or None
                    )
                    if st_result.success and st_result.data:
                        raw_posts.extend(st_result.data)
                except Exception:
                    logger.exception("KOLTrackerAgent: stocktwits_fetch failed")

        # Reddit
        if by_platform["reddit"]:
            reddit_tool = self.tools.get("reddit_fetch")
            if reddit_tool:
                try:
                    rd_result: ToolResult = await reddit_tool.fetch(tickers=tickers or None)
                    if rd_result.success and rd_result.data:
                        raw_posts.extend(rd_result.data)
                except Exception:
                    logger.exception("KOLTrackerAgent: reddit_fetch failed")

        if not raw_posts:
            logger.info("KOLTrackerAgent: no posts collected from any platform")
            state.agent_timings[self.name] = time.monotonic() - start_time
            return state

        # LLM signal extraction (batch up to 30 posts)
        signals = await self._extract_signals(raw_posts[:30])

        if not signals:
            logger.info("KOLTrackerAgent: no signals extracted by LLM")
            state.agent_timings[self.name] = time.monotonic() - start_time
            return state

        # Build handle → source_id mapping
        handle_to_source: dict[str, dict[str, Any]] = {}
        for platform_sources in by_platform.values():
            for s in platform_sources:
                handle_to_source[s["handle"]] = s

        # Write signals to state and record calls
        for sig in signals:
            ticker = sig.get("ticker", "")
            if ticker not in state.kol_signals:
                state.kol_signals[ticker] = {"signals": [], "last_updated": ""}

            # Inject reliability_score from source
            source_info = handle_to_source.get(sig.get("handle", ""), {})
            sig["reliability_score"] = source_info.get("reliability_score", 0.5)

            state.kol_signals[ticker]["signals"].append(sig)
            state.kol_signals[ticker]["last_updated"] = datetime.now(UTC).isoformat()

            # Record to kol_calls table
            if source_info:
                try:
                    await kol_store.record_call({
                        "kol_source_id": source_info["id"],
                        "ticker": ticker,
                        "direction": sig.get("direction", "neutral"),
                        "call_date": sig.get("timestamp", datetime.now(UTC).isoformat()),
                        "call_price": 0.0,  # Price not available at signal extraction time
                        "source_url": sig.get("url", ""),
                        "content_snippet": (sig.get("content", "") or "")[:200],
                    })
                except Exception:
                    logger.exception(
                        "KOLTrackerAgent: failed to record call for %s/%s",
                        source_info.get("handle"), ticker,
                    )

        # Write to Long-term Memory
        try:
            await self.memory.write(
                "long",
                {
                    "type": "kol_signals",
                    "tickers": list(state.kol_signals.keys()),
                    "signal_count": len(signals),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                ttl_days=90,
            )
        except Exception:
            logger.exception("KOLTrackerAgent: failed to write to long-term memory")

        # Write extension
        self.write_extension(state, "raw_posts_count", len(raw_posts))
        self.write_extension(state, "signals_extracted", len(signals))
        self.write_extension(state, "sources_used", len(sources))

        elapsed = time.monotonic() - start_time
        state.agent_timings[self.name] = elapsed
        logger.info(
            "KOLTrackerAgent: %d sources, %d raw posts, %d signals extracted in %.1fs",
            len(sources), len(raw_posts), len(signals), elapsed,
        )
        return state

    async def _extract_signals(self, posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Use LLM (mini) to extract structured signals from raw posts.

        Args:
            posts: Raw posts from social tools (max 30).

        Returns:
            List of signal dicts, or empty list on failure.
        """
        try:
            template = self._jinja.get_template("kol_signal_extract.j2")
            prompt = template.render(posts=posts)

            resp = await self.llm.chat(
                model=settings.LLM_MODEL_MINI,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            result = json.loads(resp.get("content", "{}"))
            return list(result.get("signals", []))
        except Exception:
            logger.exception("KOLTrackerAgent: LLM signal extraction failed")
            return []
