"""TriggerCheckRunner — hourly scan of pending triggers.

Checks active triggers against current market data, fires triggered ones,
and expires stale ones. Sends Telegram notifications for fired triggers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from loguru import logger

from aegis.storage.trigger_store import TriggerStore


class TriggerCheckRunner:
    """Hourly scanner for pending triggers.

    Reads active triggers from TriggerStore, checks conditions against
    current market data, and fires/expires as appropriate.
    """

    def __init__(
        self,
        trigger_store: TriggerStore | None = None,
        telegram_notifier: Any = None,
        ws_manager: Any = None,
    ) -> None:
        self._store = trigger_store or TriggerStore()
        self._telegram = telegram_notifier
        self._ws_manager = ws_manager

    async def run(self) -> list[dict[str, Any]]:
        """Scan all active triggers and process them.

        Returns:
            List of triggers that fired during this run.
        """
        triggers = await self._store.list_all_pending()
        if not triggers:
            logger.debug("TriggerCheckRunner: no active triggers")
            return []

        now = datetime.now(UTC)
        fired: list[dict[str, Any]] = []

        for trigger in triggers:
            trigger_id = trigger.get("id")
            if trigger_id is None:
                continue

            # Check if expired
            valid_until = trigger.get("valid_until", "")
            if valid_until:
                try:
                    valid_dt = datetime.fromisoformat(
                        valid_until.replace("Z", "+00:00")
                    )
                    if now > valid_dt:
                        await self._store.mark_expired(trigger_id)
                        logger.info(
                            f"TriggerCheckRunner: trigger {trigger_id} expired"
                        )
                        continue
                except (ValueError, TypeError):
                    pass

            # Check if triggered
            if self._is_triggered(trigger):
                await self._store.mark_triggered(trigger_id)
                fired.append(trigger)

                # Emit WebSocket event
                if self._ws_manager:
                    try:
                        await self._ws_manager.emit_trigger_fired(
                            f"trigger-{trigger_id}", trigger
                        )
                    except Exception as exc:
                        logger.error(
                            f"TriggerCheckRunner: failed to emit WS event: {exc}"
                        )

                # Send Telegram notification
                if self._telegram:
                    try:
                        await self._send_trigger_notification(trigger)
                    except Exception as exc:
                        logger.error(
                            f"TriggerCheckRunner: failed to send notification: {exc}"
                        )

        logger.info(
            f"TriggerCheckRunner: scanned {len(triggers)}, "
            f"fired {len(fired)}"
        )
        return fired

    def _is_triggered(self, trigger: dict[str, Any]) -> bool:
        """Check if a trigger's condition is met.

        Currently uses trigger_params directly. In production, this would
        fetch real-time market data to compare against thresholds.
        """
        trigger_type = trigger.get("trigger_type", "")
        params = trigger.get("trigger_params", {})

        if trigger_type == "price_below":
            current_price = params.get("_current_price")
            threshold = params.get("threshold")
            if current_price is not None and threshold is not None:
                return float(current_price) < float(threshold)

        elif trigger_type == "price_above":
            current_price = params.get("_current_price")
            threshold = params.get("threshold")
            if current_price is not None and threshold is not None:
                return float(current_price) > float(threshold)

        elif trigger_type == "rsi_below":
            current_rsi = params.get("_current_rsi")
            threshold = params.get("threshold")
            if current_rsi is not None and threshold is not None:
                return float(current_rsi) < float(threshold)

        elif trigger_type == "volume_spike":
            current_volume = params.get("_current_volume")
            avg_volume = params.get("avg_volume")
            multiplier = params.get("multiplier", 1.5)
            if current_volume is not None and avg_volume is not None:
                return float(current_volume) > float(avg_volume) * float(multiplier)

        return False

    async def _send_trigger_notification(self, trigger: dict[str, Any]) -> None:
        """Send a Telegram notification for a fired trigger."""
        if self._telegram:
            if hasattr(self._telegram, "send_trigger"):
                await self._telegram.send_trigger(trigger)
            else:
                await self._telegram.send_message(
                    f"⏰ Trigger Fired\n"
                    f"Ticker: {trigger.get('ticker', 'unknown')}\n"
                    f"Type: {trigger.get('trigger_type', 'unknown')}"
                )
