"""DataHarvesterAgent — Pipeline 入口，采集行情/宏观/新闻数据。

通过 Tool Registry 拉取外部数据，按 pipeline_mode 决定拉取深度：
- full: yFinance OHLCV + FRED 宏观 + Tavily 新闻
- lightweight: 仅 yFinance OHLCV + VIX
"""

from __future__ import annotations

from aegis.agents.base import BaseAgent
from aegis.pipeline.state import PipelineState
from aegis.registry.agent_registry import AgentManifest


class DataHarvesterAgent(BaseAgent):
    name = "data_harvester"
    manifest = AgentManifest(
        name="data_harvester",
        version="0.1.0",
        requires=[],
        provides=["market_data", "macro_data"],
        tags=["data", "harvester"],
        llm_dependency=False,
        parallel_group=None,
        pipeline_mode="both",
    )

    async def run(self, state: PipelineState) -> PipelineState:
        if not state.tickers:
            return state

        await self._fetch_market_data(state)
        await self._fetch_macro_data(state)

        if state.pipeline_mode == "full":
            await self._fetch_news(state)

        return state

    async def _fetch_market_data(self, state: PipelineState) -> None:
        """拉取行情数据（OHLCV + 实时价格）。"""
        tool = self.tools.get("yfinance")
        if tool is None:
            state.error_flags.append(
                {
                    "agent": self.name,
                    "error": "yfinance tool not found in registry",
                }
            )
            return

        for ticker in state.tickers:
            try:
                result = await tool.fetch(ticker=ticker)
                if result.success:
                    state.market_data[ticker] = result.data
                else:
                    state.error_flags.append(
                        {
                            "agent": self.name,
                            "ticker": ticker,
                            "error": f"yfinance fetch failed: {result.error}",
                        }
                    )
            except Exception as e:
                state.error_flags.append(
                    {
                        "agent": self.name,
                        "ticker": ticker,
                        "error": f"yfinance exception: {str(e)}",
                    }
                )

    async def _fetch_macro_data(self, state: PipelineState) -> None:
        """拉取宏观数据。

        full 模式: FEDFUNDS + DGS10 + VIX
        lightweight 模式: 仅 VIX
        """
        tool = self.tools.get("fred")
        if tool is None:
            state.error_flags.append(
                {
                    "agent": self.name,
                    "error": "fred tool not found in registry",
                }
            )
            return

        series = "FEDFUNDS,DGS10,VIX" if state.pipeline_mode == "full" else "VIX"

        try:
            result = await tool.fetch(series=series)
            if result.success:
                if isinstance(result.data, dict):
                    state.macro_data = result.data
                else:
                    state.macro_data = {"raw": result.data}
            else:
                state.error_flags.append(
                    {
                        "agent": self.name,
                        "error": f"fred fetch failed: {result.error}",
                    }
                )
        except Exception as e:
            state.error_flags.append(
                {
                    "agent": self.name,
                    "error": f"fred exception: {str(e)}",
                }
            )

    async def _fetch_news(self, state: PipelineState) -> None:
        """拉取新闻数据（仅 full 模式）。"""
        tool = self.tools.get("tavily")
        if tool is None:
            state.error_flags.append(
                {
                    "agent": self.name,
                    "error": "tavily tool not found in registry",
                }
            )
            return

        for ticker in state.tickers:
            try:
                result = await tool.fetch(query=f"{ticker} stock news", max_results=5)
                if result.success:
                    if ticker not in state.market_data:
                        state.market_data[ticker] = {}
                    if isinstance(state.market_data[ticker], dict):
                        state.market_data[ticker]["news"] = result.data
                else:
                    state.error_flags.append(
                        {
                            "agent": self.name,
                            "ticker": ticker,
                            "error": f"tavily fetch failed: {result.error}",
                        }
                    )
            except Exception as e:
                state.error_flags.append(
                    {
                        "agent": self.name,
                        "ticker": ticker,
                        "error": f"tavily exception: {str(e)}",
                    }
                )
