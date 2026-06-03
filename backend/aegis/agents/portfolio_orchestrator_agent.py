"""PortfolioOrchestratorAgent — 持仓加载、entry_mode 分流、基础健康分计算。

M1 简化版：从 config/mock_portfolio.json 加载 mock 持仓。
M2 升级：真实券商 API + Delta Dollars + 完整健康度。
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal, cast

from aegis.agents.base import BaseAgent
from aegis.pipeline.state import PipelineState
from aegis.registry.agent_registry import AgentManifest

_VALID_ENTRY_MODES = frozenset({"passive", "active_left", "active_right", "cc", "sell_put"})
_EntryMode = Literal["passive", "active_left", "active_right", "cc", "sell_put"]


class PortfolioOrchestratorAgent(BaseAgent):
    name = "portfolio_orchestrator"
    manifest = AgentManifest(
        name="portfolio_orchestrator",
        version="0.1.0",
        requires=[],
        provides=[
            "tickers_holdings_active",
            "tickers_holdings_passive",
            "entry_mode",
            "health_scores",
            "positions",
        ],
        tags=["portfolio", "orchestrator"],
        llm_dependency=False,
        parallel_group=None,
        pipeline_mode="both",
    )

    async def run(self, state: PipelineState) -> PipelineState:
        positions = self._load_portfolio()
        if positions is None:
            return state

        self._classify_by_entry_mode(positions, state)
        self._compute_health_scores(positions, state)
        self._populate_positions(positions, state)

        return state

    def _load_portfolio(self) -> list[dict[str, Any]] | None:
        """加载 mock 持仓数据。"""
        path = self.config.get(
            "mock_portfolio_path",
            os.path.join(os.path.dirname(__file__), "..", "..", "config", "mock_portfolio.json"),
        )
        try:
            with open(path) as f:
                data = json.load(f)
            return cast(list[dict[str, Any]], data.get("positions", []))
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, KeyError):
            return None

    def _classify_by_entry_mode(
        self, positions: list[dict[str, Any]], state: PipelineState
    ) -> None:
        """按 entry_mode 分流到 active / passive 列表。"""
        active: list[str] = []
        passive: list[str] = []

        for pos in positions:
            ticker = pos.get("ticker", "")
            mode = pos.get("entry_mode", "passive")

            if mode not in _VALID_ENTRY_MODES:
                state.error_flags.append({
                    "agent": self.name,
                    "ticker": ticker,
                    "error": f"unknown entry_mode '{mode}', defaulting to passive",
                })
                mode = "passive"

            state.entry_mode[ticker] = cast(_EntryMode, mode)

            if mode == "passive":
                passive.append(ticker)
            else:
                active.append(ticker)

        state.tickers_holdings_active = list(dict.fromkeys(active))
        state.tickers_holdings_passive = list(dict.fromkeys(passive))

    def _compute_health_scores(
        self, positions: list[dict[str, Any]], state: PipelineState
    ) -> None:
        """计算每个持仓的基础 health_score（0-100）。

        公式:
          dte_score = min(dte / 365, 1.0) * 100  (无 DTE 则 100)
          pnl_ratio = (current_price - avg_cost) / avg_cost
          pnl_score = clamp(50 + pnl_ratio * 100, 0, 100)
          health_score = 0.4 * dte_score + 0.6 * pnl_score
        """
        for pos in positions:
            ticker = pos.get("ticker", "")
            dte = pos.get("dte")
            avg_cost = pos.get("avg_cost")
            current_price = pos.get("current_price")

            # DTE score
            if dte is not None and isinstance(dte, (int, float)) and dte > 0:
                dte_score = min(dte / 365.0, 1.0) * 100.0
            else:
                dte_score = 100.0

            # PnL score
            if (
                avg_cost is not None
                and current_price is not None
                and isinstance(avg_cost, (int, float))
                and isinstance(current_price, (int, float))
                and avg_cost != 0
            ):
                pnl_ratio = (current_price - avg_cost) / avg_cost
                pnl_score = max(0.0, min(100.0, 50.0 + pnl_ratio * 100.0))
            else:
                pnl_score = 50.0
                state.error_flags.append({
                    "agent": self.name,
                    "ticker": ticker,
                    "error": "missing avg_cost or current_price, using neutral pnl_score=50",
                })

            health_score = 0.4 * dte_score + 0.6 * pnl_score
            state.health_scores[ticker] = round(health_score, 2)

    def _populate_positions(
        self, positions: list[dict[str, Any]], state: PipelineState
    ) -> None:
        """将持仓详情写入 state.positions。"""
        for pos in positions:
            ticker = pos.get("ticker", "")
            state.positions[ticker] = pos
