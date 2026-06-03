"""Tests for stop loss calculator."""

import pytest

from aegis.calculators.stop_loss import compute_stop_loss


def test_stop_loss_fixed_pct_standard():
    """Fixed 8% stop loss from entry price."""
    result = compute_stop_loss(entry_price=100.0, mode="fixed_pct")

    assert result.stop_price == 92.0
    assert result.stop_pct == 0.08
    assert result.mode == "fixed_pct"


def test_stop_loss_fixed_pct_fractional():
    """Fixed 8% stop loss with fractional entry price."""
    result = compute_stop_loss(entry_price=423.75, mode="fixed_pct")

    expected = round(423.75 * 0.92, 2)
    assert result.stop_price == expected
    assert result.stop_pct == 0.08
    assert result.mode == "fixed_pct"


def test_stop_loss_fixed_pct_small_price():
    """Fixed 8% stop loss with small entry price."""
    result = compute_stop_loss(entry_price=10.0, mode="fixed_pct")

    assert result.stop_price == 9.20
    assert result.stop_pct == 0.08


def test_stop_loss_support_based_standard():
    """Support-based stop: 2% below support level."""
    result = compute_stop_loss(
        entry_price=100.0, mode="support_based", support_level=95.0
    )

    assert result.stop_price == 93.10  # 95 * 0.98
    assert result.stop_pct == pytest.approx(0.069, rel=1e-3)
    assert result.mode == "support_based"


def test_stop_loss_support_based_tight():
    """Support-based stop with support close to entry."""
    result = compute_stop_loss(
        entry_price=100.0, mode="support_based", support_level=98.0
    )

    assert result.stop_price == 96.04  # 98 * 0.98
    assert result.stop_pct == pytest.approx(0.0396, rel=1e-3)
    assert result.mode == "support_based"


def test_stop_loss_support_based_missing_level():
    """support_based mode without support_level raises ValueError."""
    with pytest.raises(ValueError, match="support_level is required"):
        compute_stop_loss(entry_price=100.0, mode="support_based")
