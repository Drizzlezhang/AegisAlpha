"""Stop loss calculator — fixed percentage and support-based modes.

Frozen at M1. Changes require owner review.
"""

from typing import Literal

from aegis.calculators.models import StopLossResult

FIXED_PCT = 0.08  # 8% stop loss for fixed_pct mode
SUPPORT_BUFFER = 0.02  # 2% below support for support_based mode


def compute_stop_loss(
    entry_price: float,
    mode: Literal["fixed_pct", "support_based"],
    support_level: float | None = None,
) -> StopLossResult:
    """Compute stop loss price and percentage.

    Args:
        entry_price: Entry price of the position.
        mode: "fixed_pct" for 8% trailing stop, "support_based" for 2% below support.
        support_level: Required for "support_based" mode. The identified support price level.

    Returns:
        StopLossResult with stop_price, stop_pct, and mode.

    Raises:
        ValueError: If mode is "support_based" and support_level is None.
    """
    if mode == "fixed_pct":
        stop_price = entry_price * (1 - FIXED_PCT)
        return StopLossResult(
            stop_price=round(stop_price, 2),
            stop_pct=FIXED_PCT,
            mode="fixed_pct",
        )

    if mode == "support_based":
        if support_level is None:
            raise ValueError("support_level is required for support_based stop loss mode")
        stop_price = support_level * (1 - SUPPORT_BUFFER)
        stop_pct = (entry_price - stop_price) / entry_price
        return StopLossResult(
            stop_price=round(stop_price, 2),
            stop_pct=round(stop_pct, 4),
            mode="support_based",
        )

    raise ValueError(f"Unknown stop loss mode: {mode}")
