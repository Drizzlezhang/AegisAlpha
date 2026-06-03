"""Tests for Wyckoff phase detector."""

import pandas as pd
import pytest

from aegis.calculators.wyckoff import detect_wyckoff_phase


def _make_ohlcv(prices: list[float], volumes: list[float]) -> pd.DataFrame:
    """Helper to create OHLCV DataFrame from close prices and volumes."""
    data = {
        "open": prices,
        "high": [p * 1.01 for p in prices],
        "low": [p * 0.99 for p in prices],
        "close": prices,
        "volume": volumes,
    }
    return pd.DataFrame(data)


def test_wyckoff_accumulation():
    """Declining price + declining volume → accumulation."""
    # 30 bars: price declining, volume declining
    prices = [100.0 - i * 0.3 for i in range(30)]
    volumes = [1_000_000 - i * 10_000 for i in range(30)]
    df = _make_ohlcv(prices, volumes)

    result = detect_wyckoff_phase(df)

    assert result.phase == "accumulation"
    assert result.confidence > 0.5
    assert "accumulation" in result.rationale.lower()


def test_wyckoff_markup():
    """Rising price + rising volume → markup."""
    prices = [100.0 + i * 0.5 for i in range(30)]
    volumes = [1_000_000 + i * 20_000 for i in range(30)]
    df = _make_ohlcv(prices, volumes)

    result = detect_wyckoff_phase(df)

    assert result.phase == "markup"
    assert result.confidence > 0.5
    assert "markup" in result.rationale.lower()


def test_wyckoff_distribution():
    """Rising price + declining volume → distribution."""
    prices = [100.0 + i * 0.3 for i in range(30)]
    volumes = [1_500_000 - i * 15_000 for i in range(30)]
    df = _make_ohlcv(prices, volumes)

    result = detect_wyckoff_phase(df)

    assert result.phase == "distribution"
    assert result.confidence > 0.4
    assert "distribution" in result.rationale.lower()


def test_wyckoff_markdown():
    """Declining price + rising volume → markdown."""
    prices = [100.0 - i * 0.5 for i in range(30)]
    volumes = [1_000_000 + i * 25_000 for i in range(30)]
    df = _make_ohlcv(prices, volumes)

    result = detect_wyckoff_phase(df)

    assert result.phase == "markdown"
    assert result.confidence > 0.5
    assert "markdown" in result.rationale.lower()


def test_wyckoff_insufficient_data():
    """Less than LOOKBACK rows → unknown with confidence 0."""
    prices = [100.0] * 10
    volumes = [1_000_000] * 10
    df = _make_ohlcv(prices, volumes)

    result = detect_wyckoff_phase(df)

    assert result.phase == "unknown"
    assert result.confidence == 0.0


def test_wyckoff_missing_columns():
    """Missing required columns raises ValueError."""
    df = pd.DataFrame({"close": [100.0] * 30, "volume": [1_000_000] * 30})

    with pytest.raises(ValueError, match="Missing required columns"):
        detect_wyckoff_phase(df)
