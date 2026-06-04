"""Tests for trend calculator — compute_trend_score."""

from aegis.calculators.trend import compute_trend_score


def _make_ohlcv(closes: list[float]) -> dict[str, list[float]]:
    n = len(closes)
    return {
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": [1000000] * n,
    }


def test_trend_score_bullish():
    """Rising prices should produce bullish trend."""
    closes = list(range(100, 200))
    result = compute_trend_score(_make_ohlcv(closes))
    assert result["trend_direction"] == "bullish"
    assert result["trend_score"] > 50
    assert result["confidence"] > 0


def test_trend_score_bearish():
    """Falling prices should produce bearish trend."""
    closes = list(range(200, 100, -1))
    result = compute_trend_score(_make_ohlcv(closes))
    assert result["trend_direction"] == "bearish"
    assert result["trend_score"] < 50


def test_trend_score_sideways():
    """Flat prices should produce sideways trend."""
    closes = [100.0] * 100
    result = compute_trend_score(_make_ohlcv(closes))
    assert result["trend_direction"] == "sideways"
    assert 40 <= result["trend_score"] <= 60


def test_trend_score_insufficient_data():
    """Single data point should return default values."""
    result = compute_trend_score(_make_ohlcv([100.0]))
    assert result["trend_direction"] == "sideways"
    assert result["trend_score"] == 50.0
    assert result["confidence"] == 0.0


def test_trend_score_empty():
    """Empty data should return default values."""
    result = compute_trend_score(_make_ohlcv([]))
    assert result["trend_direction"] == "sideways"
    assert result["trend_score"] == 50.0
