"""Pure calculation functions for trend detection and Wyckoff phase analysis.

No LLM, no IO, no side effects.
"""

from __future__ import annotations

from typing import Any


def detect_wyckoff_phase(ohlcv: dict[str, list[float]]) -> dict[str, Any]:
    """Detect Wyckoff phase from OHLCV data using simplified price-structure analysis.

    Args:
        ohlcv: {"open": [...], "high": [...], "low": [...], "close": [...], "volume": [...]}

    Returns:
        {"phase": "accumulation"|"markup"|"distribution"|"markdown"|"unknown",
         "confidence": 0.0-1.0,
         "signals": [str, ...]}
    """
    closes = ohlcv.get("close", [])
    highs = ohlcv.get("high", [])
    lows = ohlcv.get("low", [])
    volumes = ohlcv.get("volume", [])

    if len(closes) < 20:
        return {"phase": "unknown", "confidence": 0.0, "signals": ["insufficient_data"]}

    # Use last 20 bars for phase detection
    recent_close = closes[-20:]
    recent_high = highs[-20:]
    recent_low = lows[-20:]
    recent_volume = volumes[-20:]

    # Compute simple metrics
    price_range = max(recent_high) - min(recent_low)
    if price_range == 0:
        return {"phase": "unknown", "confidence": 0.0, "signals": ["zero_price_range"]}

    current_price = recent_close[-1]
    price_position = (current_price - min(recent_low)) / price_range

    # Trend direction over the window
    first_half_avg = sum(recent_close[:10]) / 10
    second_half_avg = sum(recent_close[10:]) / 10
    trend_pct = (second_half_avg - first_half_avg) / first_half_avg if first_half_avg else 0

    # Volume trend
    first_half_vol = sum(recent_volume[:10]) / 10 if recent_volume else 0
    second_half_vol = sum(recent_volume[10:]) / 10 if recent_volume else 0
    vol_change = (second_half_vol - first_half_vol) / first_half_vol if first_half_vol else 0

    signals: list[str] = []
    phase = "unknown"
    confidence = 0.5

    if trend_pct > 0.03:
        # Uptrend
        if price_position < 0.35:
            phase = "accumulation"
            signals.append("price_in_lower_range_during_uptrend")
            signals.append("potential_accumulation_zone")
            confidence = 0.55
        elif vol_change > 0.1:
            phase = "markup"
            signals.append("rising_prices_with_increasing_volume")
            confidence = 0.65
        else:
            phase = "markup"
            signals.append("rising_prices")
            confidence = 0.55
    elif trend_pct < -0.03:
        # Downtrend
        if price_position > 0.65:
            phase = "distribution"
            signals.append("price_in_upper_range_during_downtrend")
            signals.append("potential_distribution_zone")
            confidence = 0.55
        elif vol_change > 0.1:
            phase = "markdown"
            signals.append("falling_prices_with_increasing_volume")
            confidence = 0.65
        else:
            phase = "markdown"
            signals.append("falling_prices")
            confidence = 0.55
    else:
        # Sideways
        if price_position < 0.3:
            phase = "accumulation"
            signals.append("sideways_near_lows")
            confidence = 0.45
        elif price_position > 0.7:
            phase = "distribution"
            signals.append("sideways_near_highs")
            confidence = 0.45
        else:
            phase = "unknown"
            signals.append("sideways_mid_range")
            confidence = 0.35

    return {"phase": phase, "confidence": round(confidence, 2), "signals": signals}


def _sma(values: list[float], period: int) -> list[float]:
    """Simple Moving Average."""
    if len(values) < period:
        return [sum(values) / len(values)] * len(values)
    result: list[float] = []
    for i in range(len(values)):
        if i < period - 1:
            window = values[: i + 1]
            result.append(sum(window) / len(window))
        else:
            window = values[i - period + 1 : i + 1]
            result.append(sum(window) / period)
    return result


def _ema(values: list[float], period: int) -> list[float]:
    """Exponential Moving Average."""
    if len(values) < 2:
        return values[:]
    multiplier = 2.0 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append((v - result[-1]) * multiplier + result[-1])
    return result


def _rsi(closes: list[float], period: int = 14) -> float:
    """Relative Strength Index."""
    if len(closes) < period + 1:
        return 50.0
    gains = 0.0
    losses = 0.0
    for i in range(-period, 0):
        change = closes[i] - closes[i - 1]
        if change > 0:
            gains += change
        else:
            losses -= change
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def compute_trend_score(ohlcv: dict[str, list[float]]) -> dict[str, Any]:
    """Compute trend direction and score using MA, RSI, and MACD.

    Args:
        ohlcv: {"open": [...], "high": [...], "low": [...], "close": [...], "volume": [...]}

    Returns:
        {"trend_direction": "bullish"|"bearish"|"sideways",
         "trend_score": 0-100,
         "ma_values": {"ma20": ..., "ma50": ..., "ma200": ...},
         "rsi": float,
         "macd": {"macd_line": ..., "signal_line": ..., "histogram": ...},
         "confidence": 0.0-1.0}
    """
    closes = ohlcv.get("close", [])
    if len(closes) < 2:
        return {
            "trend_direction": "sideways",
            "trend_score": 50.0,
            "ma_values": {},
            "rsi": 50.0,
            "macd": {},
            "confidence": 0.0,
        }

    n = len(closes)

    # Compute MAs
    ma20_series = _sma(closes, 20)
    ma50_series = _sma(closes, 50)
    ma200_series = _sma(closes, 200) if n >= 200 else _sma(closes, n)

    ma20 = ma20_series[-1]
    ma50 = ma50_series[-1]
    ma200 = ma200_series[-1]

    # RSI
    rsi_value = _rsi(closes)

    # MACD
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line_series = [e12 - e26 for e12, e26 in zip(ema12, ema26, strict=False)]
    signal_line_series = _ema(macd_line_series, 9)
    macd_line = macd_line_series[-1]
    signal_line = signal_line_series[-1]
    histogram = macd_line - signal_line

    # Scoring
    score = 50.0
    signals_count = 0

    # MA alignment
    if ma20 > ma50 > ma200:
        score += 15
        signals_count += 1
    elif ma20 < ma50 < ma200:
        score -= 15
        signals_count += 1

    # Price vs MA20
    current_price = closes[-1]
    if current_price > ma20:
        score += 10
        signals_count += 1
    elif current_price < ma20:
        score -= 10
        signals_count += 1

    # RSI
    if rsi_value > 60:
        score += 10
        signals_count += 1
    elif rsi_value < 40:
        score -= 10
        signals_count += 1

    # MACD
    if histogram > 0:
        score += 10
        signals_count += 1
    elif histogram < 0:
        score -= 10
        signals_count += 1

    # MACD crossover
    if len(macd_line_series) >= 2 and len(signal_line_series) >= 2:
        prev_hist = macd_line_series[-2] - signal_line_series[-2]
        if prev_hist <= 0 and histogram > 0:
            score += 5
            signals_count += 1
        elif prev_hist >= 0 and histogram < 0:
            score -= 5
            signals_count += 1

    score = max(0.0, min(100.0, score))

    if score >= 60:
        direction = "bullish"
    elif score <= 40:
        direction = "bearish"
    else:
        direction = "sideways"

    confidence = min(0.9, signals_count / 5.0) if signals_count > 0 else 0.3

    return {
        "trend_direction": direction,
        "trend_score": round(score, 1),
        "ma_values": {"ma20": round(ma20, 2), "ma50": round(ma50, 2), "ma200": round(ma200, 2)},
        "rsi": round(rsi_value, 1),
        "macd": {
            "macd_line": round(macd_line, 4),
            "signal_line": round(signal_line, 4),
            "histogram": round(histogram, 4),
        },
        "confidence": round(confidence, 2),
    }
