"""Pydantic response models for Aegis API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


class PipelineRunRequest(BaseModel):
    tickers: list[str] = []
    mode: str = "full"


class PipelineRunResponse(BaseModel):
    pipeline_id: str
    status: str = "started"


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
    condition: str
    status: str = "pending"


class TriggerCreateRequest(BaseModel):
    ticker: str
    condition: str


class AgentManifestResponse(BaseModel):
    name: str
    version: str
    tags: list[str] = []
    pipeline_mode: str = "full"
    enabled: bool = True
