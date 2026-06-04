"""Futu OpenD broker adapter.

Connects to Futu OpenD via futu-api SDK.
Requires: futu-api (pip install futu-api)
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from aegis.tools.brokers.base import BrokerAdapter, BrokerPosition
from aegis.utils.settings import settings


class FutuAdapter(BrokerAdapter):
    """Futu OpenD adapter via futu-api SDK.

    Connects to local OpenD instance:
    - FUTU_HOST: localhost (default)
    - FUTU_PORT: 11111 (default)
    - FUTU_TRADE_ENV: SIMULATE / REAL
    """

    def __init__(self) -> None:
        self._quote_ctx = None
        self._trade_ctx = None
        self._available = False
        self._init_error: str | None = None

        try:
            from futu import OpenQuoteContext, OpenTradeContext, TrdEnv

            self._TrdEnv = TrdEnv
            self._quote_ctx = OpenQuoteContext(
                host=settings.FUTU_HOST, port=settings.FUTU_PORT
            )
            self._trade_ctx = OpenTradeContext(
                host=settings.FUTU_HOST, port=settings.FUTU_PORT
            )
            self._available = True
            logger.info(
                f"FutuAdapter connected to {settings.FUTU_HOST}:{settings.FUTU_PORT} "
                f"(env={settings.FUTU_TRADE_ENV})"
            )
        except ImportError:
            self._init_error = "futu-api not installed"
            logger.warning("FutuAdapter: futu-api not installed, adapter disabled")
        except Exception as exc:
            self._init_error = str(exc)
            logger.warning(f"FutuAdapter init failed: {exc}")

    async def get_positions(self) -> list[BrokerPosition]:
        if not self._available:
            logger.warning(f"FutuAdapter unavailable: {self._init_error}")
            return []

        try:
            import asyncio

            ret, data = await asyncio.to_thread(
                self._trade_ctx.position_list_query  # type: ignore[union-attr]
            )
            if ret != 0:
                logger.error(f"Futu position_list_query failed: {data}")
                return []

            positions: list[BrokerPosition] = []
            for _, row in data.iterrows():
                pos = BrokerPosition(
                    account="futu",
                    ticker=row.get("code", ""),
                    pos_type="stock",
                    quantity=int(row.get("qty", 0)),
                    avg_cost=float(row.get("cost_price", 0)),
                    current_price=float(row.get("nominal_price", 0)) or None,
                    unrealized_pnl=float(row.get("pl_val", 0)) or None,
                )
                positions.append(pos)
            return positions
        except Exception as exc:
            logger.exception(f"FutuAdapter.get_positions failed: {exc}")
            return []

    async def get_account_summary(self) -> dict[str, Any]:
        if not self._available:
            return {}

        try:
            import asyncio

            ret, data = await asyncio.to_thread(
                self._trade_ctx.accinfo_query  # type: ignore[union-attr]
            )
            if ret != 0:
                logger.error(f"Futu accinfo_query failed: {data}")
                return {}

            row = data.iloc[0]
            return {
                "nav": float(row.get("total_assets", 0)),
                "cash": float(row.get("cash", 0)),
                "margin": float(row.get("margin", 0)),
                "market_value": float(row.get("market_val", 0)),
            }
        except Exception as exc:
            logger.exception(f"FutuAdapter.get_account_summary failed: {exc}")
            return {}

    async def get_options_chain(
        self, ticker: str, expiry: str | None = None
    ) -> list[dict[str, Any]]:
        if not self._available:
            return []

        try:
            import asyncio

            from futu import OptionType  # type: ignore[import-not-found,unused-ignore]

            results: list[dict[str, Any]] = []
            for opt_type in (OptionType.CALL, OptionType.PUT):
                ret, data = await asyncio.to_thread(
                    self._quote_ctx.get_option_chain,  # type: ignore[union-attr]
                    ticker,
                    expiry or "",
                    opt_type,
                )
                if ret == 0:
                    results.extend(data.to_dict("records"))
            return results
        except Exception as exc:
            logger.exception(f"FutuAdapter.get_options_chain failed: {exc}")
            return []

    async def get_oi_data(self, ticker: str) -> dict[str, Any]:
        chain = await self.get_options_chain(ticker)
        total_oi = sum(
            row.get("open_interest", 0) or 0
            for row in chain
        )
        return {"ticker": ticker, "total_open_interest": total_oi, "chain_size": len(chain)}
