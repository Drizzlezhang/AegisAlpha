"""Fund Flow Agent — macro liquidity, credit risk, sector rotation analysis.

Input: state.tickers, state.raw_macro_data
Output: state.fund_flow_data[ticker], state.extensions["fund_flow_agent"]
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, ClassVar, cast

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from aegis.agents.base import BaseAgent
from aegis.llm.client import LLMClient
from aegis.pipeline.state import PipelineState
from aegis.registry.agent_registry import AgentManifest
from aegis.utils.settings import settings

# Ticker → Sector ETF mapping for fund flow scoring
TICKER_SECTOR_MAP: dict[str, str] = {
    "QQQ": "XLK",
    "SPY": "SPY",
    "AAPL": "XLK",
    "MSFT": "XLK",
    "NVDA": "XLK",
    "GOOGL": "XLC",
    "AMZN": "XLY",
    "META": "XLC",
    "TSLA": "XLY",
    "JPM": "XLF",
    "XOM": "XLE",
    "JNJ": "XLV",
    "UNH": "XLV",
    "PG": "XLP",
    "HD": "XLY",
}

SECTOR_ETFS = [
    "XLK", "XLE", "XLF", "XBI", "XLV",
    "XLY", "XLI", "XLP", "XLU", "XLRE",
]


class FundFlowAgent(BaseAgent):
    """Analyzes macro liquidity, credit risk, and sector rotation.

    Calls 5 data source tools, classifies macro conditions, generates
    an LLM narrative, and scores each ticker's fund flow factor.
    """

    name = "fund_flow_agent"
    manifest = AgentManifest(
        name="fund_flow_agent",
        version="0.1.0",
        requires=["raw_macro_data"],
        provides=["fund_flow_data", "extensions.fund_flow_agent"],
        tags=["signal", "macro_flow"],
        llm_dependency=True,
        parallel_group="signal_analysts",
        pipeline_mode="full",
    )

    TICKER_SECTOR_MAP: ClassVar[dict[str, str]] = TICKER_SECTOR_MAP

    def __init__(
        self,
        memory: Any,
        tools: dict[str, Any],
        config: dict[str, Any],
    ) -> None:
        super().__init__(memory, tools, config)
        self.llm = LLMClient()
        templates_dir = Path(__file__).parent.parent.parent / "config" / "prompts"
        self._jinja = Environment(loader=FileSystemLoader(str(templates_dir)))

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self, state: PipelineState) -> PipelineState:
        """Execute fund flow analysis for all tickers."""
        start_time = time.monotonic()

        try:
            # Step 1-4: Fetch data from tools
            etf_flows = await self._fetch_etf_flows()
            sector_flows = await self._fetch_sector_flows()
            rrp_data = await self._fetch_fred("RRPONTSYD")
            tga_data = await self._fetch_fred("WTREGEN")
            hyg_lqd = await self._fetch_hyg_lqd()

            # Step 5-7: Classify
            macro_liquidity = self._classify_liquidity(rrp_data, tga_data)
            credit_appetite = self._classify_credit(hyg_lqd)
            sector_rotation = self._sector_rotation(sector_flows)

            # Step 8: LLM narrative
            narrative = await self._generate_narrative(
                macro_liquidity, credit_appetite, sector_rotation, etf_flows
            )

            # Step 9: Score each ticker
            for ticker in state.tickers:
                score = self._score_for_ticker(ticker, sector_rotation, macro_liquidity)
                state.fund_flow_data[ticker] = {
                    "fund_flow_score": score,
                    "macro_liquidity": macro_liquidity,
                    "credit_appetite": credit_appetite,
                    "sector": self.TICKER_SECTOR_MAP.get(ticker, "SPY"),
                }

            # Write extensions
            self.write_extension(state, "macro_liquidity", macro_liquidity)
            self.write_extension(state, "credit_appetite", credit_appetite)
            self.write_extension(state, "sector_rotation", sector_rotation)
            self.write_extension(state, "etf_flows_7d", etf_flows)
            self.write_extension(state, "narrative", narrative)

            logger.info(
                "FundFlowAgent: liquidity=%s credit=%s rotation_into=%s",
                macro_liquidity,
                credit_appetite,
                sector_rotation.get("into", []),
            )

        except Exception:
            logger.exception("FundFlowAgent failed")
            state.error_flags.append({
                "agent": self.name,
                "error": "FundFlowAgent unhandled exception",
            })

        elapsed = time.monotonic() - start_time
        state.agent_timings[self.name] = elapsed
        return state

    # ------------------------------------------------------------------
    # Tool fetch helpers
    # ------------------------------------------------------------------

    async def _fetch_etf_flows(self) -> dict[str, float]:
        """Fetch SPY/QQQ/GLD/SLV 7-day fund flows."""
        try:
            tool = self.tools.get("etf_flows")
            if tool is None:
                return {}
            result = await tool.fetch(symbols=["SPY", "QQQ", "GLD", "SLV"])
            if result.success and result.data:
                return {
                    sym: result.data.get(sym, {}).get("flow_7d", 0.0)
                    for sym in ["SPY", "QQQ", "GLD", "SLV"]
                }
        except Exception as e:
            logger.warning(f"ETF flows fetch failed: {e}")
        return {}

    async def _fetch_sector_flows(self) -> dict[str, float]:
        """Fetch 10 sector ETF 7-day fund flows."""
        try:
            tool = self.tools.get("sector_etf_flows")
            if tool is None:
                return {}
            result = await tool.fetch()
            if result.success and result.data:
                return {
                    sym: result.data.get(sym, {}).get("flow_7d", 0.0)
                    for sym in SECTOR_ETFS
                }
        except Exception as e:
            logger.warning(f"Sector ETF flows fetch failed: {e}")
        return {}

    async def _fetch_fred(self, series_id: str) -> dict[str, Any]:
        """Fetch a single FRED series."""
        try:
            tool = self.tools.get("fred")
            if tool is None:
                return {}
            result = await tool.fetch(series_id=series_id)
            if result.success and result.data:
                return cast(dict[str, Any], result.data)
        except Exception as e:
            logger.warning(f"FRED {series_id} fetch failed: {e}")
        return {}

    async def _fetch_hyg_lqd(self) -> dict[str, Any]:
        """Fetch HYG-LQD spread data."""
        try:
            tool = self.tools.get("hyg_lqd_spread")
            if tool is None:
                return {}
            result = await tool.fetch(period="5d")
            if result.success and result.data:
                return cast(dict[str, Any], result.data)
        except Exception as e:
            logger.warning(f"HYG-LQD fetch failed: {e}")
        return {}

    # ------------------------------------------------------------------
    # Pure classification logic
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_liquidity(rrp_data: dict[str, Any], tga_data: dict[str, Any]) -> str:
        """Classify macro liquidity based on ON RRP and TGA 7-day changes.

        ON RRP falling + TGA falling → expanding (liquidity released)
        ON RRP rising + TGA rising → tightening (liquidity drained)
        Otherwise → neutral
        """
        rrp_change = FundFlowAgent._pct_change_7d(rrp_data)
        tga_change = FundFlowAgent._pct_change_7d(tga_data)

        if rrp_change is None or tga_change is None:
            return "neutral"

        if rrp_change < -0.02 and tga_change < -0.02:
            return "expanding"
        elif rrp_change > 0.02 and tga_change > 0.02:
            return "tightening"
        else:
            return "neutral"

    @staticmethod
    def _classify_credit(hyg_lqd: dict[str, Any]) -> str:
        """Classify credit risk appetite from HYG-LQD spread data.

        Uses the pre-computed 'appetite' field from HYGLQDSpreadAdapter.
        Falls back to 'neutral' if data is unavailable.
        """
        if not hyg_lqd:
            return "neutral"
        return cast(str, hyg_lqd.get("appetite", "neutral"))

    @staticmethod
    def _sector_rotation(sector_flows: dict[str, float]) -> dict[str, Any]:
        """Identify sector rotation: top 3 inflow and top 3 outflow sectors."""
        if not sector_flows:
            return {"into": [], "out_of": []}

        sorted_flows = sorted(sector_flows.items(), key=lambda x: x[1], reverse=True)
        into = [s[0] for s in sorted_flows[:3] if s[1] > 0]
        out_of = [s[0] for s in sorted_flows[-3:] if s[1] < 0]
        # Reverse out_of so most negative is first
        out_of.reverse()

        return {"into": into, "out_of": out_of}

    @staticmethod
    def _score_for_ticker(
        ticker: str, rotation: dict[str, Any], liquidity: str
    ) -> float:
        """Score a ticker's fund flow factor (0-100).

        - Sector in rotation.into + liquidity expanding → 80+
        - Sector in rotation.out_of + liquidity tightening → 20-
        - Other combinations → 40-60
        """
        sector = TICKER_SECTOR_MAP.get(ticker, "SPY")
        base_score = 50.0

        into = rotation.get("into", [])
        out_of = rotation.get("out_of", [])

        if sector in into:
            base_score += 20
        elif sector in out_of:
            base_score -= 20

        if liquidity == "expanding":
            base_score += 15
        elif liquidity == "tightening":
            base_score -= 15

        return max(0.0, min(100.0, base_score))

    # ------------------------------------------------------------------
    # LLM narrative
    # ------------------------------------------------------------------

    async def _generate_narrative(
        self,
        macro_liquidity: str,
        credit_appetite: str,
        sector_rotation: dict[str, Any],
        etf_flows: dict[str, float],
    ) -> str:
        """Generate 1-2 sentence natural language summary via LLM."""
        try:
            template = self._jinja.get_template("fund_flow_narrative.j2")
            prompt = template.render(
                macro_liquidity=macro_liquidity,
                credit_appetite=credit_appetite,
                sector_rotation=sector_rotation,
                etf_flows_7d=etf_flows,
            )
            resp = await self.llm.chat(
                model=settings.LLM_MODEL_MINI,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
            return cast(str, resp["content"].strip())
        except Exception as e:
            logger.warning(f"Fund flow narrative generation failed: {e}")
            return self._fallback_narrative(
                macro_liquidity, credit_appetite, sector_rotation
            )

    @staticmethod
    def _fallback_narrative(
        macro_liquidity: str,
        credit_appetite: str,
        sector_rotation: dict[str, Any],
    ) -> str:
        """Rule-based fallback narrative when LLM is unavailable."""
        into = sector_rotation.get("into", [])
        out_of = sector_rotation.get("out_of", [])

        parts = [
            f"Macro liquidity: {macro_liquidity}.",
            f"Credit appetite: {credit_appetite}.",
        ]
        if into:
            parts.append(f"Capital flowing into: {', '.join(into)}.")
        if out_of:
            parts.append(f"Capital flowing out of: {', '.join(out_of)}.")

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _pct_change_7d(data: dict[str, Any]) -> float | None:
        """Calculate 7-day percentage change from FRED observations."""
        observations = data.get("observations", [])
        if len(observations) < 2:
            return None

        # FRED returns desc-sorted; take first and ~7th
        latest_val = observations[0].get("value")
        # Find a value ~7 days ago (FRED has daily data, so index 6 or 7)
        idx = min(7, len(observations) - 1)
        past_val = observations[idx].get("value")

        if latest_val == "." or past_val == ".":
            return None

        try:
            latest = float(latest_val)
            past = float(past_val)
            if past == 0:
                return None
            return (latest - past) / abs(past)
        except (ValueError, TypeError):
            return None
