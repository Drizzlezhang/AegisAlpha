"""Tests for GEX calculator."""

import pandas as pd
import pytest

from aegis.calculators.gex import compute_gex


def _make_chain(
    strikes: list[float],
    gammas: list[float],
    ois: list[int],
    types: list[str] | None = None,
) -> pd.DataFrame:
    """Helper to create options chain DataFrame."""
    if types is None:
        types = ["call"] * len(strikes)
    return pd.DataFrame(
        {
            "strike": strikes,
            "option_type": types,
            "gamma": gammas,
            "open_interest": ois,
        }
    )


def test_gex_basic():
    """Basic GEX computation with a few strikes."""
    df = _make_chain(
        strikes=[400.0, 410.0, 420.0],
        gammas=[0.002, 0.003, 0.002],
        ois=[10000, 15000, 10000],
    )
    spot = 415.0

    result = compute_gex(df, spot)

    # GEX_i = gamma * OI * spot * 100
    # strike 400: 0.002 * 10000 * 415 * 100 = 830,000
    # strike 410: 0.003 * 15000 * 415 * 100 = 1,867,500
    # strike 420: 0.002 * 10000 * 415 * 100 = 830,000
    # total = 3,527,500
    assert result.total_gex == pytest.approx(3_527_500, rel=1e-4)
    assert len(result.gex_by_strike) == 3
    assert result.gex_by_strike[410.0] == pytest.approx(1_867_500, rel=1e-4)


def test_gex_gamma_flip():
    """Gamma Flip: cumulative GEX crosses from positive to negative."""
    df = _make_chain(
        strikes=[400.0, 410.0, 420.0, 430.0],
        gammas=[0.003, 0.002, -0.001, -0.004],
        ois=[10000, 10000, 20000, 15000],
    )
    spot = 415.0

    result = compute_gex(df, spot)

    # strike 400: 0.003 * 10000 * 415 * 100 = 1,245,000
    # strike 410: 0.002 * 10000 * 415 * 100 = 830,000
    # strike 420: -0.001 * 20000 * 415 * 100 = -830,000
    # strike 430: -0.004 * 15000 * 415 * 100 = -2,490,000
    # Cumulative: 1,245,000 → 2,075,000 → 1,245,000 → -1,245,000
    # Crosses between 420 and 430
    assert result.gamma_flip is not None
    assert 420.0 < result.gamma_flip < 430.0


def test_gex_max_pain():
    """Max Pain: strike with maximum total open interest."""
    df = _make_chain(
        strikes=[400.0, 410.0, 420.0],
        gammas=[0.002, 0.003, 0.002],
        ois=[10000, 25000, 15000],
    )
    spot = 415.0

    result = compute_gex(df, spot)

    assert result.max_pain == 410.0  # Highest OI


def test_gex_max_pain_mixed_calls_puts():
    """Max Pain aggregates call + put OI at each strike."""
    df = pd.DataFrame(
        {
            "strike": [400.0, 400.0, 410.0, 410.0],
            "option_type": ["call", "put", "call", "put"],
            "gamma": [0.002, 0.002, 0.003, 0.003],
            "open_interest": [10000, 8000, 12000, 15000],
        }
    )
    spot = 405.0

    result = compute_gex(df, spot)

    # strike 400: OI = 18000, strike 410: OI = 27000
    assert result.max_pain == 410.0


def test_gex_missing_columns():
    """Missing required columns raises ValueError."""
    df = pd.DataFrame({"strike": [400.0], "gamma": [0.002]})

    with pytest.raises(ValueError, match="Missing required columns"):
        compute_gex(df, spot=415.0)


def test_gex_no_gamma_flip():
    """All positive GEX → no gamma flip."""
    df = _make_chain(
        strikes=[400.0, 410.0, 420.0],
        gammas=[0.002, 0.003, 0.001],
        ois=[10000, 15000, 10000],
    )
    spot = 415.0

    result = compute_gex(df, spot)

    assert result.gamma_flip is None
    assert result.total_gex > 0
