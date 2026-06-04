"""Pure calculation functions for support/resistance levels and volume profile.

No LLM, no IO, no side effects.
"""

from __future__ import annotations

from typing import Any


def find_support_resistance(ohlcv: dict[str, list[float]]) -> dict[str, Any]:
    """Identify support and resistance levels from OHLCV data using swing points.

    Args:
        ohlcv: {"open": [...], "high": [...], "low": [...], "close": [...], "volume": [...]}

    Returns:
        {"support_levels": [float, ...],
         "resistance_levels": [float, ...],
         "key_levels": [{"price": float, "type": "support"|"resistance", "strength": 0-100}, ...]}
    """
    highs = ohlcv.get("high", [])
    lows = ohlcv.get("low", [])

    if len(highs) < 5:
        return {"support_levels": [], "resistance_levels": [], "key_levels": []}

    n = len(highs)
    lookback = min(5, n // 3) if n >= 15 else 2

    # Find swing highs and swing lows
    swing_highs: list[dict[str, Any]] = []
    swing_lows: list[dict[str, Any]] = []

    for i in range(lookback, n - lookback):
        # Swing high: higher than surrounding bars
        is_swing_high = True
        for j in range(1, lookback + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_swing_high = False
                break
        if is_swing_high:
            swing_highs.append({"price": highs[i], "index": i, "touches": 1})

        # Swing low: lower than surrounding bars
        is_swing_low = True
        for j in range(1, lookback + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_swing_low = False
                break
        if is_swing_low:
            swing_lows.append({"price": lows[i], "index": i, "touches": 1})

    # Cluster nearby levels (within 1% tolerance)
    def _cluster_levels(
        levels: list[dict[str, Any]], tolerance_pct: float = 0.01
    ) -> list[dict[str, Any]]:
        if not levels:
            return []
        sorted_levels = sorted(levels, key=lambda x: x["price"])
        clusters: list[dict[str, Any]] = []
        current_cluster = {
            "price": sorted_levels[0]["price"],
            "touches": sorted_levels[0]["touches"],
            "count": 1,
        }
        for lvl in sorted_levels[1:]:
            price_diff = abs(lvl["price"] - current_cluster["price"])
            if price_diff / current_cluster["price"] < tolerance_pct:
                current_cluster["price"] = (
                    current_cluster["price"] * current_cluster["count"] + lvl["price"]
                ) / (current_cluster["count"] + 1)
                current_cluster["touches"] += lvl["touches"]
                current_cluster["count"] += 1
            else:
                clusters.append(current_cluster)
                current_cluster = {
                    "price": lvl["price"],
                    "touches": lvl["touches"],
                    "count": 1,
                }
        clusters.append(current_cluster)
        return clusters

    support_clusters = _cluster_levels(swing_lows)
    resistance_clusters = _cluster_levels(swing_highs)

    # Sort by touches (strength)
    support_clusters.sort(key=lambda x: x["touches"], reverse=True)
    resistance_clusters.sort(key=lambda x: x["touches"], reverse=True)

    # Build key_levels with strength scores
    max_touches = max([c["touches"] for c in support_clusters + resistance_clusters] or [1])

    key_levels: list[dict[str, Any]] = []
    for c in support_clusters[:5]:
        strength = min(100, int(c["touches"] / max_touches * 100))
        key_levels.append({"price": round(c["price"], 2), "type": "support", "strength": strength})
    for c in resistance_clusters[:5]:
        strength = min(100, int(c["touches"] / max_touches * 100))
        key_levels.append(
            {"price": round(c["price"], 2), "type": "resistance", "strength": strength}
        )

    # Sort key_levels by price ascending
    key_levels.sort(key=lambda x: x["price"])

    support_levels = sorted([round(c["price"], 2) for c in support_clusters[:5]])
    resistance_levels = sorted([round(c["price"], 2) for c in resistance_clusters[:5]])

    return {
        "support_levels": support_levels,
        "resistance_levels": resistance_levels,
        "key_levels": key_levels,
    }


def compute_volume_profile(ohlcv: dict[str, list[float]]) -> dict[str, Any]:
    """Compute volume profile: POC, value area, and volume nodes.

    Args:
        ohlcv: {"open": [...], "high": [...], "low": [...], "close": [...], "volume": [...]}

    Returns:
        {"poc": float,
         "value_area_high": float,
         "value_area_low": float,
         "volume_nodes": [{"price": float, "volume": float}, ...]}
    """
    highs = ohlcv.get("high", [])
    lows = ohlcv.get("low", [])
    closes = ohlcv.get("close", [])
    volumes = ohlcv.get("volume", [])

    if len(closes) < 2:
        return {"poc": 0.0, "value_area_high": 0.0, "value_area_low": 0.0, "volume_nodes": []}

    # Use last 60 bars or all available
    n = min(60, len(closes))
    recent_high = highs[-n:]
    recent_low = lows[-n:]
    recent_volume = volumes[-n:]

    price_min = min(recent_low)
    price_max = max(recent_high)
    if price_max == price_min:
        return {
            "poc": round(price_max, 2),
            "value_area_high": round(price_max, 2),
            "value_area_low": round(price_min, 2),
            "volume_nodes": [],
        }

    # Create price bins (20 bins)
    num_bins = 20
    bin_size = (price_max - price_min) / num_bins
    bins: dict[int, float] = dict.fromkeys(range(num_bins), 0.0)

    for i in range(n):
        # Distribute volume across the bar's range
        bar_low = recent_low[i]
        bar_high = recent_high[i]
        bar_vol = recent_volume[i] if i < len(recent_volume) else 0
        if bar_high == bar_low:
            bin_idx = min(num_bins - 1, int((bar_low - price_min) / bin_size))
            bins[bin_idx] += bar_vol
        else:
            vol_per_bin = bar_vol / max(1, int((bar_high - bar_low) / bin_size + 1))
            low_bin = max(0, int((bar_low - price_min) / bin_size))
            high_bin = min(num_bins - 1, int((bar_high - price_min) / bin_size))
            for b in range(low_bin, high_bin + 1):
                bins[b] += vol_per_bin

    # Find POC (price with highest volume)
    poc_bin = max(bins, key=bins.get)  # type: ignore[arg-type]
    poc = price_min + (poc_bin + 0.5) * bin_size

    # Value area (70% of total volume)
    total_vol = sum(bins.values())
    if total_vol == 0:
        return {
            "poc": round(poc, 2),
            "value_area_high": round(price_max, 2),
            "value_area_low": round(price_min, 2),
            "volume_nodes": [],
        }

    # Sort bins by volume descending
    sorted_bins = sorted(bins.items(), key=lambda x: x[1], reverse=True)
    cumulative = 0.0
    value_area_bins: set[int] = set()
    for bin_idx, vol in sorted_bins:
        cumulative += vol
        value_area_bins.add(bin_idx)
        if cumulative / total_vol >= 0.70:
            break

    va_high = price_min + (max(value_area_bins) + 1) * bin_size
    va_low = price_min + min(value_area_bins) * bin_size

    # Volume nodes
    volume_nodes = [
        {"price": round(price_min + (b + 0.5) * bin_size, 2), "volume": round(v, 2)}
        for b, v in sorted(bins.items(), key=lambda x: x[1], reverse=True)[:5]
        if v > 0
    ]

    return {
        "poc": round(poc, 2),
        "value_area_high": round(va_high, 2),
        "value_area_low": round(va_low, 2),
        "volume_nodes": volume_nodes,
    }
