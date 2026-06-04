"""Pydantic response models for Aegis API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.2.0"


class PipelineRunRequest(BaseModel):
    tickers: list[str] = []
    mode: str = "full"


class PipelineRunResponse(BaseModel):
    pipeline_id: str
    status: str = "started"


class PipelineTriggerRequest(BaseModel):
    tickers: list[str] = []
    mode: str = "full"  # "full" or "lightweight"


class PipelineTriggerResponse(BaseModel):
    pipeline_id: str
    status: str = "started"
    mode: str = "full"


class PipelineLatestResponse(BaseModel):
    pipeline_id: str = ""
    mode: str = "manual"
    tickers: list[str] = []
    recommendations: list[dict[str, Any]] = []
    health_scores: dict[str, float] = {}


class PositionResponse(BaseModel):
    ticker: str
    quantity: float = 0.0
    avg_cost: float = 0.0
    entry_mode: str = "passive"


class PortfolioHealthResponse(BaseModel):
    health_scores: dict[str, float] = {}
    alerts: list[dict[str, Any]] = []
    total_tickers: int = 0


class DeltaDollarsResponse(BaseModel):
    total_delta_dollars: float = 0.0
    budget_pct: float = 0.30
    budget_used_pct: float = 0.0
    by_ticker: dict[str, float] = {}


class RecommendationResponse(BaseModel):
    ticker: str
    action: str
    strategy: str
    rationale: str = ""
    score: float = 0.0
    urgency: str = "medium"


class TriggerResponse(BaseModel):
    id: int
    ticker: str
    trigger_type: str = ""
    trigger_params: dict[str, Any] = {}
    suggested_action: dict[str, Any] = {}
    status: str = "pending"
    created_at: str = ""
    valid_until: str = ""
    fired_at: str | None = None


class TriggerCreateRequest(BaseModel):
    ticker: str
    trigger_type: str = "price_below"
    trigger_params: dict[str, Any] = {}
    suggested_action: dict[str, Any] = {}
    valid_until: str = ""


class AgentManifestResponse(BaseModel):
    name: str
    version: str
    tags: list[str] = []
    pipeline_mode: str = "full"
    enabled: bool = True
    llm_dependency: bool = True
    parallel_group: str | None = None


class FlowETFResponse(BaseModel):
    ticker: str
    net_flow: float = 0.0
    flow_pct: float = 0.0
    period: str = "5d"


class FlowSectorResponse(BaseModel):
    sector: str
    rotation_score: float = 0.0
    flow_direction: str = "neutral"


class FlowSmartMoneyResponse(BaseModel):
    ticker: str
    score: float = 0.0
    direction: str = "neutral"
    unusual_options: int = 0
