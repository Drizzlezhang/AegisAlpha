"""Pure calculation functions for GEX (Gamma Exposure) analysis.

No LLM, no IO, no side effects.
"""
from __future__ import annotations

from typing import Any


def analyze_gex(gex_data: dict[str, Any]) -> dict[str, Any]:
    """Analyze GEX data to identify gamma flip level and key strike concentrations.

    Args:
        gex_data: {
            "total_gex": float,           # Total gamma exposure in dollars
            "spot_price": float,          # Current underlying price
            "strike_distribution": [      # Gamma distribution by strike
                {"strike": float, "gamma": float, "oi": int},
                ...
            ],
        }

    Returns:
        {"gamma_flip_level": float | None,
         "key_strikes": [float, ...],
         "net_gex_signal": "positive"|"negative"|"neutral"}
    """
    total_gex = gex_data.get("total_gex", 0.0)
    strikes = gex_data.get("strike_distribution", [])

    if not strikes:
        return _empty_result()

    # Find gamma flip level: the strike where cumulative gamma crosses zero
    sorted_strikes = sorted(strikes, key=lambda x: x["strike"])
    cumulative = 0.0
    gamma_flip_level: float | None = None

    for i, s in enumerate(sorted_strikes):
        cumulative += s.get("gamma", 0.0)
        if gamma_flip_level is None and cumulative >= 0 and i > 0:
            # Interpolate the flip level
            prev_cum = cumulative - s.get("gamma", 0.0)
            if prev_cum < 0:
                prev_strike = sorted_strikes[i - 1]["strike"]
                curr_strike = s["strike"]
                denom = abs(prev_cum) + abs(cumulative)
                ratio = abs(prev_cum) / denom if denom != 0 else 0.5
                gamma_flip_level = prev_strike + ratio * (curr_strike - prev_strike)

    # Key strikes: highest absolute gamma concentration
    key_strikes_raw = sorted(strikes, key=lambda x: abs(x.get("gamma", 0.0)), reverse=True)
    key_strikes = [s["strike"] for s in key_strikes_raw[:5]]

    # Net GEX signal
    if total_gex > 0:
        net_signal = "positive"
    elif total_gex < 0:
        net_signal = "negative"
    else:
        net_signal = "neutral"

    return {
        "gamma_flip_level": round(gamma_flip_level, 2) if gamma_flip_level is not None else None,
        "key_strikes": [round(k, 2) for k in key_strikes],
        "net_gex_signal": net_signal,
    }


def _empty_result() -> dict[str, Any]:
    return {
        "gamma_flip_level": None,
        "key_strikes": [],
        "net_gex_signal": "neutral",
    }
