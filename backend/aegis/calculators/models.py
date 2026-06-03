"""Frozen at M1. Changes require owner review.

Shared Pydantic result models for all calculator modules.
"""

from typing import Literal

from pydantic import BaseModel, Field


class GreeksResult(BaseModel):
    """Black-Scholes Greeks + implied volatility."""

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_volatility: float


class StopLossResult(BaseModel):
    """Stop loss price and percentage."""

    stop_price: float
    stop_pct: float
    mode: Literal["fixed_pct", "support_based"]


class WyckoffResult(BaseModel):
    """Wyckoff phase detection result."""

    phase: Literal["accumulation", "distribution", "markup", "markdown", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


class GexResult(BaseModel):
    """Gamma Exposure aggregation result."""

    total_gex: float
    gamma_flip: float | None = None
    max_pain: float | None = None
    gex_by_strike: dict[float, float] = Field(default_factory=dict)


class VolumeProfileResult(BaseModel):
    """Volume profile with POC and Value Area."""

    poc: float
    value_area_high: float
    value_area_low: float
    profile: dict[float, float] = Field(default_factory=dict)
