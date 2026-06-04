"""Tests for Volume Profile calculator."""

import pandas as pd
import pytest

from aegis.calculators.volume_profile import compute_volume_profile


def _make_ohlcv(prices: list[float], volumes: list[float]) -> pd.DataFrame:
    """Helper to create OHLCV DataFrame."""
    return pd.DataFrame(
        {
            "open": prices,
            "high": [p * 1.02 for p in prices],
            "low": [p * 0.98 for p in prices],
            "close": prices,
            "volume": volumes,
        }
    )


def test_volume_profile_basic():
    """Basic volume profile with concentrated volume at one level."""
    # 20 bars all at ~100 with varying volume
    prices = [100.0 + i * 0.1 for i in range(20)]
    volumes = [1000] * 10 + [5000] * 5 + [1000] * 5  # Peak in middle
    df = _make_ohlcv(prices, volumes)

    result = compute_volume_profile(df, bins=20)

    # POC should be near the high-volume region
    assert 100.0 < result.poc < 102.0
    assert result.value_area_low < result.poc < result.value_area_high
    assert len(result.profile) > 0


def test_volume_profile_poc():
    """POC should be at the price level with highest volume."""
    # 10 bars at price 100 with volume 1000, 10 bars at price 110 with volume 5000
    prices = [100.0] * 10 + [110.0] * 10
    volumes = [1000] * 10 + [5000] * 10
    df = _make_ohlcv(prices, volumes)

    result = compute_volume_profile(df, bins=20)

    # POC should be near 110 (higher volume)
    assert result.poc > 105.0


def test_volume_profile_value_area():
    """Value Area should cover ~70% of total volume."""
    prices = [100.0] * 10 + [105.0] * 10 + [110.0] * 10
    volumes = [1000] * 10 + [3000] * 10 + [1000] * 10
    df = _make_ohlcv(prices, volumes)

    result = compute_volume_profile(df, bins=30)

    # VA should span a reasonable range
    va_range = result.value_area_high - result.value_area_low
    assert va_range > 0
    # POC should be within VA
    assert result.value_area_low <= result.poc <= result.value_area_high


def test_volume_profile_empty():
    """Empty DataFrame returns zeros."""
    df = pd.DataFrame({"high": [], "low": [], "close": [], "volume": []})

    result = compute_volume_profile(df)

    assert result.poc == 0.0
    assert result.value_area_high == 0.0
    assert result.value_area_low == 0.0
    assert result.profile == {}


def test_volume_profile_bins_out_of_range():
    """bins < 10 or > 500 raises ValueError."""
    df = _make_ohlcv([100.0] * 20, [1000] * 20)

    with pytest.raises(ValueError, match="bins must be between"):
        compute_volume_profile(df, bins=5)

    with pytest.raises(ValueError, match="bins must be between"):
        compute_volume_profile(df, bins=501)


def test_volume_profile_missing_columns():
    """Missing required columns raises ValueError."""
    df = pd.DataFrame({"close": [100.0] * 20})

    with pytest.raises(ValueError, match="Missing required columns"):
        compute_volume_profile(df)


def test_volume_profile_single_price():
    """All prices identical → single bin profile."""
    df = pd.DataFrame(
        {
            "open": [100.0] * 20,
            "high": [100.0] * 20,
            "low": [100.0] * 20,
            "close": [100.0] * 20,
            "volume": [1000] * 20,
        }
    )

    result = compute_volume_profile(df, bins=20)

    assert result.poc == 100.0
    assert result.value_area_high == result.value_area_low
    assert len(result.profile) == 1
