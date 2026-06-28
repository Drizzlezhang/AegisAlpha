"""KOL Attribution Service — post-hoc P&L attribution and reliability update.

Runs daily via APScheduler. Evaluates pending KOL calls after 30 days,
updates reliability scores via EMA, and provides 60-day supplementary P&L.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from aegis.tools.base import ToolResult


class KOLAttributionService:
    """Post-hoc attribution for KOL signal calls.

    Flow:
      1. Get pending calls older than 30 days from KOLStore
      2. For each call, get current price via price_fetcher
      3. Calculate P&L: (current_price - call_price) / call_price * 100
      4. Determine status:
         - bullish + P&L > +5% → validated
         - bearish + P&L < -5% → invalidated (bearish was wrong, price went up)
         - bearish + P&L < -5% → validated (bearish was right, price went down)
         - otherwise → invalidated
      5. EMA update reliability_score: new = 0.9 * old + 0.1 * (1 if validated else 0)
      6. 60-day supplementary P&L update for calls with 30d attribution but no 60d P&L
    """

    # Attribution thresholds
    VALIDATION_THRESHOLD_PCT: float = 5.0  # 5% price move threshold
    EMA_ALPHA: float = 0.9  # Smoothing factor for reliability EMA
    MAX_CALLS_PER_RUN: int = 200  # Cap to prevent timeout

    def __init__(
        self,
        kol_store: Any,
        price_fetcher: Any | None = None,
    ) -> None:
        """Initialize attribution service.

        Args:
            kol_store: KOLStore instance for CRUD operations.
            price_fetcher: Callable(ticker) -> float | None for current price.
                           Defaults to YFinanceAdapter().fetch(method="quote").
        """
        self._store = kol_store
        self._price_fetcher = price_fetcher

    async def _get_current_price(self, ticker: str) -> float | None:
        """Get current price for a ticker.

        Returns:
            Current price as float, or None if unavailable.
        """
        if self._price_fetcher is None:
            return None

        try:
            result: ToolResult = await self._price_fetcher.fetch(
                ticker=ticker, method="quote"
            )
            if result.success and isinstance(result.data, dict):
                price = result.data.get("price")
                if price is not None:
                    return float(price)
        except Exception:
            logger.exception("KOLAttribution: price fetch failed for %s", ticker)

        return None

    async def run_30d_attribution(self) -> dict[str, int]:
        """Run 30-day attribution for all pending calls.

        Returns:
            Dict with counts: {total, validated, invalidated, skipped, errors}.
        """
        stats = {"total": 0, "validated": 0, "invalidated": 0, "skipped": 0, "errors": 0}

        try:
            pending = await self._store.get_pending_attribution(days_ago=30)
        except Exception:
            logger.exception("KOLAttribution: failed to get pending calls")
            return stats

        if not pending:
            logger.info("KOLAttribution: no pending calls for 30d attribution")
            return stats

        # Cap to prevent timeout
        calls_to_process = pending[: self.MAX_CALLS_PER_RUN]
        stats["total"] = len(calls_to_process)

        for call in calls_to_process:
            try:
                # Get current price
                current_price = await self._get_current_price(call.ticker)
                if current_price is None or current_price <= 0:
                    logger.debug(
                        "KOLAttribution: skipping call %d (%s) — no price",
                        call.id, call.ticker,
                    )
                    stats["skipped"] += 1
                    continue

                # Calculate P&L
                if call.call_price > 0:
                    pnl_pct = (current_price - call.call_price) / call.call_price * 100
                else:
                    pnl_pct = 0.0

                # Determine validation status
                if call.direction == "bullish":
                    validated = pnl_pct > self.VALIDATION_THRESHOLD_PCT
                elif call.direction == "bearish":
                    validated = pnl_pct < -self.VALIDATION_THRESHOLD_PCT
                else:
                    validated = False

                status = "validated" if validated else "invalidated"

                # Update call attribution
                await self._store.update_attribution(call.id, status, round(pnl_pct, 2))

                # Update source reliability via EMA
                await self._update_reliability(call.kol_source_id, validated)

                if validated:
                    stats["validated"] += 1
                else:
                    stats["invalidated"] += 1

            except Exception:
                logger.exception(
                    "KOLAttribution: error processing call %d", call.id
                )
                stats["errors"] += 1

        logger.info(
            "KOLAttribution 30d: total=%d validated=%d invalidated=%d skipped=%d errors=%d",
            stats["total"], stats["validated"], stats["invalidated"],
            stats["skipped"], stats["errors"],
        )
        return stats

    async def run_60d_supplementary(self) -> dict[str, int]:
        """Run 60-day supplementary P&L update for calls with 30d attribution.

        Returns:
            Dict with counts: {total, updated, skipped, errors}.
        """
        stats = {"total": 0, "updated": 0, "skipped": 0, "errors": 0}

        try:
            needs_update = await self._store.get_calls_needing_60d_update()
        except Exception:
            logger.exception("KOLAttribution: failed to get calls needing 60d update")
            return stats

        if not needs_update:
            logger.info("KOLAttribution: no calls needing 60d P&L update")
            return stats

        calls_to_process = needs_update[: self.MAX_CALLS_PER_RUN]
        stats["total"] = len(calls_to_process)

        for call in calls_to_process:
            try:
                current_price = await self._get_current_price(call.ticker)
                if current_price is None or current_price <= 0:
                    stats["skipped"] += 1
                    continue

                if call.call_price > 0:
                    pnl_pct = (current_price - call.call_price) / call.call_price * 100
                else:
                    pnl_pct = 0.0

                await self._store.update_pnl_60d(call.id, round(pnl_pct, 2))
                stats["updated"] += 1

            except Exception:
                logger.exception(
                    "KOLAttribution: error updating 60d P&L for call %d", call.id
                )
                stats["errors"] += 1

        logger.info(
            "KOLAttribution 60d: total=%d updated=%d skipped=%d errors=%d",
            stats["total"], stats["updated"], stats["skipped"], stats["errors"],
        )
        return stats

    async def _update_reliability(self, source_id: int, validated: bool) -> None:
        """Update KOL source reliability via EMA smoothing.

        new_score = EMA_ALPHA * old_score + (1 - EMA_ALPHA) * (1 if validated else 0)
        Clamped to [0, 1].
        """
        try:
            source = await self._store.get_source(source_id)
            if source is None:
                logger.warning(
                    "KOLAttribution: source %d not found for reliability update",
                    source_id,
                )
                return

            old_score = source.reliability_score
            increment = 1.0 if validated else 0.0
            new_score = self.EMA_ALPHA * old_score + (1 - self.EMA_ALPHA) * increment
            new_score = max(0.0, min(1.0, new_score))

            await self._store.update_source(source_id, {
                "reliability_score": round(new_score, 4),
                "total_calls": source.total_calls + 1,
                "successful_calls": source.successful_calls + (1 if validated else 0),
            })

            logger.debug(
                "KOLAttribution: source %d reliability %.4f → %.4f (%s)",
                source_id, old_score, new_score,
                "validated" if validated else "invalidated",
            )
        except Exception:
            logger.exception(
                "KOLAttribution: failed to update reliability for source %d",
                source_id,
            )

    async def get_attribution_report(
        self, source_id: int | None = None
    ) -> dict[str, Any]:
        """Get attribution statistics report.

        Args:
            source_id: Optional filter by KOL source.

        Returns:
            Dict with stats and source details.
        """
        try:
            stats = await self._store.get_attribution_stats(source_id=source_id)
        except Exception:
            logger.exception("KOLAttribution: failed to get attribution stats")
            return {"total": 0, "validated": 0, "invalidated": 0, "pending": 0}

        total = stats.get("total", 0)
        validated = stats.get("validated", 0)
        accuracy = (validated / total * 100) if total > 0 else 0.0

        report: dict[str, Any] = {
            "total_calls": total,
            "validated": validated,
            "invalidated": stats.get("invalidated", 0),
            "pending": stats.get("pending", 0),
            "accuracy_pct": round(accuracy, 2),
        }

        # Add source details if filtering
        if source_id:
            try:
                source = await self._store.get_source(source_id)
                if source:
                    report["source"] = {
                        "id": source.id,
                        "name": source.name,
                        "platform": source.platform,
                        "handle": source.handle,
                        "reliability_score": source.reliability_score,
                        "total_calls": source.total_calls,
                        "successful_calls": source.successful_calls,
                    }
            except Exception:
                pass

        return report
