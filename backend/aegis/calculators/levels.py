"""Pure calculation functions for support/resistance levels.

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
