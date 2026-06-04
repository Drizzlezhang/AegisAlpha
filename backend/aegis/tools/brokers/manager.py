"""BrokerManager — multi-broker aggregation.

Manages multiple BrokerAdapter instances, queries them in parallel,
and aggregates results with graceful degradation.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from aegis.tools.brokers.base import BrokerAdapter, BrokerPosition


class BrokerManager:
    """Aggregate positions from multiple broker adapters.

    Queries all adapters in parallel via asyncio.gather.
    Single broker failure does not block others.
    """

    def __init__(self, adapters: list[BrokerAdapter]) -> None:
        self._adapters = adapters

    async def get_all_positions(self) -> list[BrokerPosition]:
        """Query all brokers in parallel, merge results.

        Returns:
            Combined list of BrokerPosition from all available brokers.
            Failed brokers are logged and skipped.
        """
        if not self._adapters:
            logger.warning("BrokerManager: no adapters configured")
            return []

        results = await asyncio.gather(
            *[a.get_positions() for a in self._adapters],
            return_exceptions=True,
        )

        positions: list[BrokerPosition] = []
        for adapter, result in zip(self._adapters, results, strict=False):
            if isinstance(result, Exception):
                logger.warning(
                    f"Broker {adapter.__class__.__name__} failed: {result}"
                )
                continue
            positions.extend(result)  # type: ignore[arg-type]

        logger.info(
            f"BrokerManager: {len(positions)} positions from "
            f"{len(self._adapters)} brokers"
        )
        return positions

    async def get_merged_summary(self) -> dict[str, Any]:
        """Merge account summaries from all brokers.

        Returns:
            Dict with total_nav, total_cash, total_margin, total_market_value.
        """
        if not self._adapters:
            return {"total_nav": 0, "total_cash": 0, "total_margin": 0, "total_market_value": 0}

        results = await asyncio.gather(
            *[a.get_account_summary() for a in self._adapters],
            return_exceptions=True,
        )

        merged: dict[str, float] = {
            "total_nav": 0.0,
            "total_cash": 0.0,
            "total_margin": 0.0,
            "total_market_value": 0.0,
        }

        for adapter, result in zip(self._adapters, results, strict=False):
            if isinstance(result, Exception):
                logger.warning(
                    f"Broker {adapter.__class__.__name__} summary failed: {result}"
                )
                continue
            if isinstance(result, dict):
                merged["total_nav"] += float(result.get("nav", 0))
                merged["total_cash"] += float(result.get("cash", 0))
                merged["total_margin"] += float(result.get("margin", 0))
                merged["total_market_value"] += float(result.get("market_value", 0))

        return merged

    @staticmethod
    def aggregate_delta_dollars(positions: list[BrokerPosition]) -> float:
        """Sum delta_dollars across all positions."""
        return sum(p.delta_dollars or 0.0 for p in positions)
