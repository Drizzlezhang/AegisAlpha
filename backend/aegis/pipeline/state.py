"""Frozen at M2 v1.3. Changes require owner review."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


def merge_dicts(left: dict, right: dict) -> dict:
    """Reducer: deep-merge two dicts for parallel agent writes."""
    merged = left.copy()
    merged.update(right)
    return merged


def merge_lists(left: list, right: list) -> list:
    """Reducer: concatenate two lists for parallel agent writes."""
    return left + right

PipelineMode = Literal["pre-market", "post-market", "manual"]


class FactorScore(BaseModel):
    factor: str
    score: float  # 0-100
    confidence: float  # 0-1
    rationale: str = ""


class OptionContract(BaseModel):
    symbol: str
    type: Literal["call", "put"]
    strike: float
    expiration: str  # YYYY-MM-DD
    dte: int
    bid: float
    ask: float
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float


class Recommendation(BaseModel):
    ticker: str
    action: Literal["buy", "sell", "hold", "close", "add", "reduce"]
    strategy: str  # "leaps_call" / "covered_call" / "stock"
    rationale: str
    factor_scores: list[FactorScore] = []
    option_contracts: list[OptionContract] = []
    stop_loss: dict[str, Any] = {}
    urgency: Literal["high", "medium", "low"] = "medium"
    score: float = 0.0
    delta_dollars_delta: float = 0.0  # v1.2: 该推荐增加的 Delta 暴露


class BlockedRecommendation(BaseModel):
    recommendation: Recommendation
    block_reason: str
    blocked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ScenarioPnL(BaseModel):
    """Scenario P&L simulation results for an option plan."""
    target: dict[str, float] = {}       # {price, pnl, pnl_pct}
    flat_30d: dict[str, float] = {}     # {price, pnl, theta_decay}
    flat_60d: dict[str, float] = {}
    flat_90d: dict[str, float] = {}
    stop_loss: dict[str, float] = {}    # {price, pnl, pnl_pct}


class StopLossPlan(BaseModel):
    """Structured stop-loss plan."""
    mode: Literal["support_based", "fixed_pct"]
    trigger_price: float
    support_level: float | None = None
    drop_pct_from_entry: float | None = None
    notes: str = ""


class PendingTrigger(BaseModel):
    """Conditional trigger for price/RSI/volume-based alerts."""
    id: int | None = None
    ticker: str
    trigger_type: Literal["price_below", "price_above", "rsi_below", "volume_spike"]
    trigger_params: dict[str, Any] = Field(default_factory=dict)
    suggested_action: dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "triggered", "expired", "cancelled"] = "pending"
    created_at: str = ""
    valid_until: str = ""
    fired_at: str | None = None


class PipelineEvent(BaseModel):
    """WebSocket pipeline event."""
    event_type: Literal["agent_start", "agent_complete", "agent_failed", "pipeline_complete", "trigger_fired"]
    pipeline_id: str
    agent_name: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = ""


class PipelineState(BaseModel):
    # 元数据
    pipeline_id: str = ""
    mode: PipelineMode = "manual"
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tickers: list[str] = []

    # v1.2: 双 Pipeline 模式
    pipeline_mode: Literal["full", "lightweight"] = "full"
    tickers_holdings_active: list[str] = []
    tickers_holdings_passive: list[str] = []
    entry_mode: dict[str, Literal["passive", "active_left", "active_right", "cc", "sell_put"]] = {}

    # 数据采集
    market_data: dict[str, Any] = {}
    macro_data: dict[str, Any] = {}
    positions: dict[str, Any] = {}

    # 分析结果
    analyst_outputs: dict[str, dict[str, Any]] = {}
    debate_results: dict[str, dict[str, Any]] = {}
    options_step1: dict[str, dict[str, Any]] = {}
    options_step2: dict[str, dict[str, Any]] = {}

    # 决策
    recommendations: list[Recommendation] = []
    blocked_recommendations: list[BlockedRecommendation] = []

    # v1.2: extensions slot（新 Agent 写自定义产出）
    extensions: Annotated[dict[str, dict[str, Any]], merge_dicts] = Field(default_factory=dict)

    # v1.2: Pending Triggers（M1 仅占位）
    pending_triggers: list[dict[str, Any]] = []

    # v1.2: Lightweight Pipeline 输出
    passive_health_alerts: list[dict[str, Any]] = []
    health_scores: dict[str, float] = {}
    delta_dollars_delta: float = 0.0

    # Working Memory
    scratchpad: dict[str, str] = {}  # {agent_name: reasoning_trace}

    # 错误
    error_flags: Annotated[list[dict[str, Any]], merge_lists] = Field(default_factory=list)

    # 性能
    agent_timings: Annotated[dict[str, float], merge_dicts] = Field(default_factory=dict)

    # v1.3: M2 新增字段
    smart_money_data: dict[str, dict[str, Any]] = {}
    fund_flow_data: dict[str, dict[str, Any]] = {}
    trigger_conditions: list[dict[str, Any]] = []
    broker_positions: dict[str, list[dict[str, Any]]] = {}
    strategy_comparisons: dict[str, list[dict[str, Any]]] = {}
    scenario_pnl: dict[str, dict[str, Any]] = {}
