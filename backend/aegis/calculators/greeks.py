"""Pure calculation functions for option Greeks using Black-Scholes model.

No LLM, no IO, no side effects.
"""
from __future__ import annotations

import math
from typing import Any


def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _compute_single_greeks(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    sigma: float,
    option_type: str,
) -> dict[str, float]:
    """Compute Greeks for a single option contract using Black-Scholes."""
    if time_to_expiry <= 0 or sigma <= 0 or spot <= 0 or strike <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "iv": sigma}

    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * sigma * sigma) * time_to_expiry) / (
        sigma * math.sqrt(time_to_expiry)
    )
    d2 = d1 - sigma * math.sqrt(time_to_expiry)

    if option_type == "call":
        delta = _norm_cdf(d1)
        theta = (
            -spot * _norm_pdf(d1) * sigma / (2 * math.sqrt(time_to_expiry))
            - risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * _norm_cdf(d2)
        ) / 365.0
    else:
        delta = _norm_cdf(d1) - 1.0
        theta = (
            -spot * _norm_pdf(d1) * sigma / (2 * math.sqrt(time_to_expiry))
            + risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * _norm_cdf(-d2)
        ) / 365.0

    gamma = _norm_pdf(d1) / (spot * sigma * math.sqrt(time_to_expiry))
    vega = spot * _norm_pdf(d1) * math.sqrt(time_to_expiry) / 100.0

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 4),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "iv": round(sigma, 4),
    }


def compute_greeks(option_chain: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute Greeks for each contract in an option chain.

    Args:
        option_chain: [
            {
                "strike": float,
                "type": "call" | "put",
                "expiration": "YYYY-MM-DD",
                "bid": float,
                "ask": float,
                "iv": float,           # implied volatility
                "spot_price": float,   # underlying spot price
                "dte": int,            # days to expiration
                "oi": int,             # open interest (optional)
                "volume": int,         # volume (optional)
            },
            ...
        ]

    Returns:
        Same list with added greek fields: delta, gamma, theta, vega
    """
    risk_free_rate = 0.05  # 5% assumed risk-free rate

    results: list[dict[str, Any]] = []
    for contract in option_chain:
        strike = contract.get("strike", 0.0)
        option_type = contract.get("type", "call")
        iv = contract.get("iv", 0.2)
        spot_price = contract.get("spot_price", 0.0)
        dte = contract.get("dte", 0)

        time_to_expiry = dte / 365.0

        greeks = _compute_single_greeks(
            spot=spot_price,
            strike=strike,
            time_to_expiry=time_to_expiry,
            risk_free_rate=risk_free_rate,
            sigma=iv,
            option_type=option_type,
        )

        result = {**contract, **greeks}
        results.append(result)

    return results
