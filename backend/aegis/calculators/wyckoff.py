"""Wyckoff phase detection via heuristic price/volume/volatility analysis.

Frozen at M1. Changes require owner review.

Algorithm:
  1. Compute price trend (linear regression slope over lookback window).
  2. Compute volume trend (linear regression slope over lookback window).
  3. Compute volatility trend (ATR change direction).
  4. Detect price-volume divergence.
  5. Map to Wyckoff phase via rule matrix.
"""

from typing import Literal

import numpy as np
import pandas as pd

from aegis.calculators.models import WyckoffResult

LOOKBACK = 20  # Default lookback window for trend computation


def _linear_slope(series: np.ndarray) -> float:
    """Compute linear regression slope of a 1-D array."""
    n = len(series)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=float)
    x_mean = x.mean()
    y_mean = series.mean()
    num = ((x - x_mean) * (series - y_mean)).sum()
    den = ((x - x_mean) ** 2).sum()
    if abs(den) < 1e-12:
        return 0.0
    return float(num / den)


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Compute Average True Range."""
    n = len(close)
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    # Simple moving average of TR
    atr_vals = np.zeros(n)
    if n > period:
        atr_vals[period] = tr[1 : period + 1].mean()
        for i in range(period + 1, n):
            atr_vals[i] = (atr_vals[i - 1] * (period - 1) + tr[i]) / period
    return atr_vals


def detect_wyckoff_phase(ohlcv_df: pd.DataFrame) -> WyckoffResult:
    """Detect Wyckoff phase from OHLCV data.

    Args:
        ohlcv_df: DataFrame with columns: open, high, low, close, volume.
                  Must have at least LOOKBACK rows.

    Returns:
        WyckoffResult with phase, confidence, and rationale.

    Raises:
        ValueError: If required columns are missing or insufficient data.
    """
    required_cols = {"open", "high", "low", "close", "volume"}
    missing = required_cols - set(ohlcv_df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if len(ohlcv_df) < LOOKBACK:
        return WyckoffResult(
            phase="unknown",
            confidence=0.0,
            rationale=f"Insufficient data: need at least {LOOKBACK} rows, got {len(ohlcv_df)}",
        )

    close = ohlcv_df["close"].values
    volume = ohlcv_df["volume"].values
    high = ohlcv_df["high"].values
    low = ohlcv_df["low"].values

    # Use last LOOKBACK bars for trend analysis
    recent_close = close[-LOOKBACK:]
    recent_volume = volume[-LOOKBACK:]

    # 1. Price trend slope (normalized by mean price)
    price_slope = _linear_slope(recent_close)
    mean_price = recent_close.mean()
    price_trend = price_slope / mean_price if mean_price > 0 else 0.0

    # 2. Volume trend slope (normalized by mean volume)
    vol_slope = _linear_slope(recent_volume.astype(float))
    mean_vol = recent_volume.mean()
    volume_trend = vol_slope / mean_vol if mean_vol > 0 else 0.0

    # 3. Volatility trend (ATR change)
    atr_vals = _atr(high, low, close)
    recent_atr = atr_vals[-LOOKBACK:]
    atr_slope = _linear_slope(recent_atr)
    mean_atr = recent_atr.mean()
    volatility_trend = atr_slope / mean_atr if mean_atr > 0 else 0.0

    # 4. Price-volume divergence
    # Positive divergence: price flat/down but volume rising (accumulation signal)
    # Negative divergence: price flat/up but volume declining (distribution signal)
    price_direction = 1 if price_trend > 0.001 else (-1 if price_trend < -0.001 else 0)
    vol_direction = 1 if volume_trend > 0.001 else (-1 if volume_trend < -0.001 else 0)
    divergence = price_direction != vol_direction and price_direction != 0 and vol_direction != 0

    # Rule matrix mapping
    threshold = 0.001  # Threshold for "flat" vs trending

    phase: Literal["accumulation", "distribution", "markup", "markdown", "unknown"]
    confidence: float
    rationale: str

    if price_trend < -threshold:
        # Price declining
        if volume_trend < -threshold or abs(volume_trend) <= threshold:
            # Declining or flat volume + declining price → Accumulation (selling exhaustion)
            phase = "accumulation"
            confidence = 0.65
            rationale = (
                f"Price declining (slope={price_trend:.4f}), "
                f"volume declining/flat (slope={volume_trend:.4f}), "
                f"volatility declining (slope={volatility_trend:.4f}) — "
                f"consistent with accumulation (selling exhaustion)"
            )
        else:
            # Rising volume + declining price → Markdown
            phase = "markdown"
            confidence = 0.70
            rationale = (
                f"Price declining (slope={price_trend:.4f}), "
                f"volume rising (slope={volume_trend:.4f}) — "
                f"consistent with markdown (distribution in progress)"
            )
    elif price_trend > threshold:
        # Price rising
        if volume_trend > threshold:
            # Rising volume + rising price → Markup
            phase = "markup"
            confidence = 0.70
            rationale = (
                f"Price rising (slope={price_trend:.4f}), "
                f"volume rising (slope={volume_trend:.4f}) — "
                f"consistent with markup (accumulation complete, trending up)"
            )
        else:
            # Flat/declining volume + rising price → Distribution
            phase = "distribution"
            confidence = 0.60
            rationale = (
                f"Price rising (slope={price_trend:.4f}), "
                f"volume declining/flat (slope={volume_trend:.4f}) — "
                f"consistent with distribution (buying exhaustion)"
            )
    else:
        # Price flat — check volume and volatility for context
        if divergence:
            if vol_direction > 0:
                phase = "accumulation"
                confidence = 0.50
                rationale = "Price flat, volume rising — possible accumulation"
            else:
                phase = "distribution"
                confidence = 0.50
                rationale = "Price flat, volume declining — possible distribution"
        else:
            phase = "unknown"
            confidence = 0.30
            rationale = (
                f"Price flat (slope={price_trend:.4f}), "
                f"no clear volume signal — unable to determine phase"
            )

    # Adjust confidence based on volatility trend alignment
    if volatility_trend < -threshold and phase == "accumulation":
        confidence = min(confidence + 0.10, 1.0)
    elif volatility_trend > threshold and phase in ("markup", "markdown"):
        confidence = min(confidence + 0.05, 1.0)

    return WyckoffResult(phase=phase, confidence=round(confidence, 2), rationale=rationale)
