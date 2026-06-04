"""Tests for levels calculator — find_support_resistance."""

from aegis.calculators.levels import find_support_resistance


def _make_ohlcv(highs: list[float], lows: list[float]) -> dict[str, list[float]]:
    n = len(highs)
    return {
        "open": [(h + lo) / 2 for h, lo in zip(highs, lows, strict=True)],
        "high": highs,
        "low": lows,
        "close": [(h + lo) / 2 for h, lo in zip(highs, lows, strict=True)],
        "volume": [1000000] * n,
    }


def test_find_support_resistance_standard():
    """Should identify support and resistance levels from swing points."""
    highs = [100, 105, 110, 108, 112, 110, 115, 113, 118, 115,
             120, 118, 122, 120, 125, 122, 128, 125, 130, 128]
    lows = [95, 98, 102, 100, 105, 103, 108, 106, 110, 108,
            112, 110, 115, 113, 118, 115, 120, 118, 122, 120]
    result = find_support_resistance(_make_ohlcv(highs, lows))
    assert "support_levels" in result
    assert "resistance_levels" in result
    assert "key_levels" in result
    assert isinstance(result["support_levels"], list)
    assert isinstance(result["resistance_levels"], list)


def test_find_support_resistance_insufficient_data():
    """Less than 5 bars should return empty levels."""
    highs = [100, 105, 110]
    lows = [95, 100, 105]
    result = find_support_resistance(_make_ohlcv(highs, lows))
    assert result["support_levels"] == []
    assert result["resistance_levels"] == []
    assert result["key_levels"] == []


def test_find_support_resistance_empty():
    """Empty data should return empty levels."""
    result = find_support_resistance(_make_ohlcv([], []))
    assert result["support_levels"] == []
    assert result["resistance_levels"] == []
    assert result["key_levels"] == []


def test_find_support_resistance_key_levels_sorted():
    """Key levels should be sorted by price ascending."""
    highs = [100, 105, 110, 108, 112, 110, 115, 113, 118, 115,
             120, 118, 122, 120, 125, 122, 128, 125, 130, 128]
    lows = [95, 98, 102, 100, 105, 103, 108, 106, 110, 108,
            112, 110, 115, 113, 118, 115, 120, 118, 122, 120]
    result = find_support_resistance(_make_ohlcv(highs, lows))
    prices = [k["price"] for k in result["key_levels"]]
    assert prices == sorted(prices)
