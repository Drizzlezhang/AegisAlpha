"""Gamma Exposure (GEX) calculator.

Frozen at M1. Changes require owner review.

Algorithm:
  - GEX_i = gamma_i × open_interest_i × spot × 100
  - Aggregate by strike: gex_by_strike[strike] = sum(GEX_i)
  - total_gex = sum(all GEX_i)
  - Gamma Flip: strike where cumulative GEX crosses from positive to negative (linear interpolation)
  - Max Pain: strike with maximum total open interest (call + put)
"""

import pandas as pd

from aegis.calculators.models import GexResult


def compute_gex(options_chain_df: pd.DataFrame, spot: float) -> GexResult:
    """Compute Gamma Exposure aggregation from an options chain.

    Args:
        options_chain_df: DataFrame with columns:
            strike, option_type, gamma, open_interest.
        spot: Current spot price of the underlying.

    Returns:
        GexResult with total_gex, gamma_flip, max_pain, gex_by_strike.

    Raises:
        ValueError: If required columns are missing.
    """
    required_cols = {"strike", "option_type", "gamma", "open_interest"}
    missing = required_cols - set(options_chain_df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = options_chain_df.copy()

    # Compute per-row GEX
    df["gex"] = df["gamma"] * df["open_interest"] * spot * 100

    # Aggregate by strike
    gex_by_strike_series = df.groupby("strike")["gex"].sum()
    gex_by_strike: dict[float, float] = {
        float(k): float(v) for k, v in gex_by_strike_series.items()
    }

    total_gex = float(df["gex"].sum())

    # Gamma Flip: find where cumulative GEX crosses from positive to negative
    strikes_sorted = sorted(gex_by_strike.keys())
    gamma_flip: float | None = None

    if len(strikes_sorted) >= 2:
        cumulative = 0.0
        for i, strike in enumerate(strikes_sorted):
            cumulative += gex_by_strike[strike]
            if cumulative < 0 and i > 0:
                # Crossed from positive to negative between strikes[i-1] and strikes[i]
                prev_strike = strikes_sorted[i - 1]
                prev_cum = cumulative - gex_by_strike[strike]
                # Linear interpolation
                if abs(prev_cum - cumulative) > 1e-12:
                    gamma_flip = prev_strike + (prev_cum / (prev_cum - cumulative)) * (
                        strike - prev_strike
                    )
                else:
                    gamma_flip = float(strike)
                break

    # Max Pain: strike with maximum total open interest
    oi_by_strike = df.groupby("strike")["open_interest"].sum()
    max_pain: float | None = None
    if len(oi_by_strike) > 0:
        max_pain = float(oi_by_strike.idxmax())

    return GexResult(
        total_gex=total_gex,
        gamma_flip=gamma_flip,
        max_pain=max_pain,
        gex_by_strike=gex_by_strike,
    )
