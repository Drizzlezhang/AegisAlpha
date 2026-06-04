"""Longbridge OpenAPI broker adapter.

Connects to Longbridge via longbridge OpenAPI SDK.
Requires: longbridge (pip install longbridge)
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from aegis.tools.brokers.base import BrokerAdapter, BrokerPosition


class LongbridgeAdapter(BrokerAdapter):
    """Longbridge OpenAPI adapter.

    Config:
    - LONGBRIDGE_APP_KEY
    - LONGBRIDGE_APP_SECRET
    - LONGBRIDGE_ACCESS_TOKEN
    - LONGBRIDGE_REGION: us
    """

    def __init__(self) -> None:
        self._trade_ctx = None
        self._available = False
        self._init_error: str | None = None

        try:
            from longbridge.openapi import Config, TradeContext

            config = Config.from_env()
            self._trade_ctx = TradeContext(config)
            self._available = True
            logger.info("LongbridgeAdapter connected")
        except ImportError:
            self._init_error = "longbridge SDK not installed"
            logger.warning("LongbridgeAdapter: longbridge SDK not installed, adapter disabled")
        except Exception as exc:
            self._init_error = str(exc)
            logger.warning(f"LongbridgeAdapter init failed: {exc}")

    async def get_positions(self) -> list[BrokerPosition]:
        if not self._available:
            logger.warning(f"LongbridgeAdapter unavailable: {self._init_error}")
            return []

        try:
            import asyncio

            resp = await asyncio.to_thread(
                self._trade_ctx.stock_positions  # type: ignore[union-attr]
            )
            positions: list[BrokerPosition] = []
            for channel in getattr(resp, "channels", []):
                for pos in getattr(channel, "positions", []):
                    positions.append(
                        BrokerPosition(
                            account="longbridge",
                            ticker=getattr(pos, "symbol", ""),
                            pos_type="stock",
                            quantity=int(getattr(pos, "quantity", 0)),
                            avg_cost=float(getattr(pos, "cost_price", 0)),
                            current_price=float(getattr(pos, "current_price", 0)) or None,
                            unrealized_pnl=float(getattr(pos, "unrealized_pl", 0)) or None,
                        )
                    )
            return positions
        except Exception as exc:
            logger.exception(f"LongbridgeAdapter.get_positions failed: {exc}")
            return []

    async def get_account_summary(self) -> dict[str, Any]:
        if not self._available:
            return {}

        try:
            import asyncio

            resp = await asyncio.to_thread(
                self._trade_ctx.account_balance  # type: ignore[union-attr]
            )
            return {
                "nav": float(getattr(resp, "total_assets", 0)),
                "cash": float(getattr(resp, "cash", 0)),
                "margin": float(getattr(resp, "margin", 0)),
                "market_value": float(getattr(resp, "market_value", 0)),
            }
        except Exception as exc:
            logger.exception(f"LongbridgeAdapter.get_account_summary failed: {exc}")
            return {}

    async def get_options_chain(
        self, ticker: str, expiry: str | None = None
    ) -> list[dict[str, Any]]:
        logger.warning("LongbridgeAdapter.get_options_chain not implemented")
        return []

    async def get_oi_data(self, ticker: str) -> dict[str, Any]:
        logger.warning("LongbridgeAdapter.get_oi_data not implemented")
        return {"ticker": ticker, "total_open_interest": 0}
