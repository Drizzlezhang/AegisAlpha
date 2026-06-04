"""Tiger Open API broker adapter.

Connects to Tiger Brokers via tigeropen SDK.
Requires: tigeropen (pip install tigeropen)
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from aegis.tools.brokers.base import BrokerAdapter, BrokerPosition
from aegis.utils.settings import settings


class TigerAdapter(BrokerAdapter):
    """Tiger Open API adapter.

    Config:
    - TIGER_ID
    - TIGER_ACCOUNT
    - TIGER_PRIVATE_KEY_PATH
    """

    def __init__(self) -> None:
        self._client = None
        self._available = False
        self._init_error: str | None = None

        try:
            from tigeropen.common.consts import Language
            from tigeropen.tiger_open_config import TigerOpenClientConfig
            from tigeropen.trade.trade_client import TradeClient

            config = TigerOpenClientConfig()
            config.tiger_id = settings.TIGER_TIGER_ID
            config.account = settings.TIGER_ACCOUNT
            config.private_key_path = settings.TIGER_PRIVATE_KEY_PATH
            config.language = Language.en_US

            self._client = TradeClient(config)
            self._available = True
            logger.info("TigerAdapter connected")
        except ImportError:
            self._init_error = "tigeropen SDK not installed"
            logger.warning("TigerAdapter: tigeropen SDK not installed, adapter disabled")
        except Exception as exc:
            self._init_error = str(exc)
            logger.warning(f"TigerAdapter init failed: {exc}")

    async def get_positions(self) -> list[BrokerPosition]:
        if not self._available:
            logger.warning(f"TigerAdapter unavailable: {self._init_error}")
            return []

        try:
            import asyncio

            resp = await asyncio.to_thread(
                self._client.get_positions  # type: ignore[union-attr]
            )
            positions: list[BrokerPosition] = []
            for item in getattr(resp, "items", []):
                positions.append(
                    BrokerPosition(
                        account="tiger",
                        ticker=getattr(item, "symbol", ""),
                        pos_type="stock",
                        quantity=int(getattr(item, "quantity", 0)),
                        avg_cost=float(getattr(item, "average_cost", 0)),
                        current_price=float(getattr(item, "market_price", 0)) or None,
                        unrealized_pnl=float(getattr(item, "unrealized_pnl", 0)) or None,
                    )
                )
            return positions
        except Exception as exc:
            logger.exception(f"TigerAdapter.get_positions failed: {exc}")
            return []

    async def get_account_summary(self) -> dict[str, Any]:
        if not self._available:
            return {}

        try:
            import asyncio

            resp = await asyncio.to_thread(
                self._client.get_assets  # type: ignore[union-attr]
            )
            return {
                "nav": float(getattr(resp, "net_liquidation", 0)),
                "cash": float(getattr(resp, "cash", 0)),
                "margin": float(getattr(resp, "margin", 0)),
                "market_value": float(getattr(resp, "market_value", 0)),
            }
        except Exception as exc:
            logger.exception(f"TigerAdapter.get_account_summary failed: {exc}")
            return {}

    async def get_options_chain(
        self, ticker: str, expiry: str | None = None
    ) -> list[dict[str, Any]]:
        logger.warning("TigerAdapter.get_options_chain not implemented")
        return []

    async def get_oi_data(self, ticker: str) -> dict[str, Any]:
        logger.warning("TigerAdapter.get_oi_data not implemented")
        return {"ticker": ticker, "total_open_interest": 0}
