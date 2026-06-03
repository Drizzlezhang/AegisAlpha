"""Volume Profile calculator — POC, Value Area, and volume distribution.

Frozen at M1. Changes require owner review.

Algorithm:
  1. Divide price range [low, high] into `bins` equal-width intervals.
  2. Assign each bar's volume to the bin containing (high+low)/2.
  3. POC = midpoint of the bin with the highest volume.
  4. Value Area: expand from POC outward until cumulative volume >= 70% of total.
"""

import pandas as pd

from aegis.calculators.models import VolumeProfileResult

MIN_BINS = 10
MAX_BINS = 500


def compute_volume_profile(ohlcv_df: pd.DataFrame, bins: int = 50) -> VolumeProfileResult:
    """Compute volume profile from OHLCV data.

    Args:
        ohlcv_df: DataFrame with columns: open, high, low, close, volume.
        bins: Number of price bins (10-500, default 50).

    Returns:
        VolumeProfileResult with poc, value_area_high, value_area_low, profile.

    Raises:
        ValueError: If required columns are missing or bins out of range.
    """
    required_cols = {"high", "low", "close", "volume"}
    missing = required_cols - set(ohlcv_df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if bins < MIN_BINS or bins > MAX_BINS:
        raise ValueError(f"bins must be between {MIN_BINS} and {MAX_BINS}, got {bins}")

    if len(ohlcv_df) == 0:
        return VolumeProfileResult(
            poc=0.0,
            value_area_high=0.0,
            value_area_low=0.0,
            profile={},
        )

    high = ohlcv_df["high"].values
    low = ohlcv_df["low"].values
    volume = ohlcv_df["volume"].values

    price_min = float(low.min())
    price_max = float(high.max())

    if price_max <= price_min:
        # All prices identical — single bin
        total_vol = float(volume.sum())
        mid = (price_min + price_max) / 2
        return VolumeProfileResult(
            poc=mid,
            value_area_high=mid,
            value_area_low=mid,
            profile={mid: total_vol},
        )

    bin_width = (price_max - price_min) / bins

    # Initialize volume per bin
    bin_volumes: dict[int, float] = dict.fromkeys(range(bins), 0.0)

    for i in range(len(ohlcv_df)):
        # Assign volume to bin containing the bar's midpoint
        mid_price = (high[i] + low[i]) / 2
        bin_idx = int((mid_price - price_min) / bin_width)
        # Clamp to valid range
        bin_idx = max(0, min(bin_idx, bins - 1))
        bin_volumes[bin_idx] += float(volume[i])

    total_volume = sum(bin_volumes.values())
    if total_volume == 0:
        return VolumeProfileResult(
            poc=0.0,
            value_area_high=0.0,
            value_area_low=0.0,
            profile={},
        )

    # POC: bin with max volume
    poc_bin = max(bin_volumes, key=lambda k: bin_volumes[k])
    poc = price_min + (poc_bin + 0.5) * bin_width

    # Value Area: expand from POC outward until 70% cumulative volume
    target_vol = total_volume * 0.70
    accumulated = bin_volumes[poc_bin]
    left = poc_bin - 1
    right = poc_bin + 1

    while accumulated < target_vol and (left >= 0 or right < bins):
        # Pick the side with more volume
        left_vol = bin_volumes.get(left, 0.0) if left >= 0 else -1.0
        right_vol = bin_volumes.get(right, 0.0) if right < bins else -1.0

        if left_vol >= right_vol and left >= 0:
            accumulated += left_vol
            left -= 1
        elif right < bins:
            accumulated += right_vol
            right += 1
        else:
            break

    va_low_bin = max(0, left + 1)
    va_high_bin = min(bins - 1, right - 1)

    value_area_low = price_min + va_low_bin * bin_width
    value_area_high = price_min + (va_high_bin + 1) * bin_width

    # Build profile dict: {price_level_midpoint: volume}
    profile: dict[float, float] = {}
    for bin_idx, vol in bin_volumes.items():
        if vol > 0:
            price_level = price_min + (bin_idx + 0.5) * bin_width
            profile[round(price_level, 2)] = round(vol, 2)

    return VolumeProfileResult(
        poc=round(poc, 2),
        value_area_high=round(value_area_high, 2),
        value_area_low=round(value_area_low, 2),
        profile=profile,
    )
