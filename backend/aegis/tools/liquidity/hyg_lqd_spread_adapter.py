"""HYG-LQD Spread adapter — credit risk appetite via high-yield vs investment-grade spread."""

from __future__ import annotations

from typing import Any

import yfinance as yf
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult


class HYGLQDSpreadAdapter(BaseTool):
    """Adapter for HYG-LQD credit spread calculation.

    Uses yfinance to fetch HYG and LQD closing prices, then computes
    the price ratio (HYG / LQD) and its change over the specified period.

    Price ratio interpretation:
    - Ratio rising → HYG outperforming LQD → risk_on
    - Ratio falling → HYG underperforming LQD → risk_off
    - Change within ±0.5% → neutral
    """

    name = "hyg_lqd_spread"

    async def fetch(self, **kwargs: Any) -> ToolResult:
        period: str = kwargs.get("period", "5d")

        try:
            hyg = yf.Ticker("HYG")
            lqd = yf.Ticker("LQD")

            hyg_hist = hyg.history(period=period)
            lqd_hist = lqd.history(period=period)

            if hyg_hist.empty or lqd_hist.empty:
                return ToolResult(
                    success=False,
                    error="No price data available for HYG or LQD",
                    source=self.name,
                )

            hyg_prices: list[float] = hyg_hist["Close"].tolist()
            lqd_prices: list[float] = lqd_hist["Close"].tolist()

            if len(hyg_prices) < 2 or len(lqd_prices) < 2:
                return ToolResult(
                    success=False,
                    error="Insufficient price data points",
                    source=self.name,
                )

            current_ratio = hyg_prices[-1] / lqd_prices[-1]
            ratio_start = hyg_prices[0] / lqd_prices[0]
            change_pct = (current_ratio - ratio_start) / ratio_start

            # Classify credit appetite
            if change_pct > 0.005:
                appetite = "risk_on"
            elif change_pct < -0.005:
                appetite = "risk_off"
            else:
                appetite = "neutral"

            data = {
                "hyg_price": round(hyg_prices[-1], 2),
                "lqd_price": round(lqd_prices[-1], 2),
                "current_ratio": round(current_ratio, 6),
                "ratio_start": round(ratio_start, 6),
                "change_pct": round(change_pct, 6),
                "appetite": appetite,
                "period": period,
            }

            logger.info(
                f"HYG-LQD Spread: ratio={current_ratio:.4f}, "
                f"change={change_pct:.4%}, appetite={appetite}"
            )
            return ToolResult(success=True, data=data, source=self.name)

        except Exception as e:
            logger.warning(f"HYG-LQD Spread fetch failed: {e}")
            return ToolResult(success=False, error=str(e), source=self.name)
