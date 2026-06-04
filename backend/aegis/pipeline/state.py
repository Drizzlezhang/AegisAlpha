"""Frozen at M1 v1.2. Changes require owner review."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

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
    extensions: dict[str, dict[str, Any]] = {}

    # v1.2: Pending Triggers（M1 仅占位）
    pending_triggers: list[dict[str, Any]] = []

    # v1.2: Lightweight Pipeline 输出
    passive_health_alerts: list[dict[str, Any]] = []
    health_scores: dict[str, float] = {}
    delta_dollars_delta: float = 0.0

    # Working Memory
    scratchpad: dict[str, str] = {}  # {agent_name: reasoning_trace}

    # 错误
    error_flags: list[dict[str, Any]] = []

    # 性能
    agent_timings: dict[str, float] = {}
