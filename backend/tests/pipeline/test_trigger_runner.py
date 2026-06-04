"""Tests for TriggerCheckRunner — hourly trigger scanning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from aegis.pipeline.trigger_runner import TriggerCheckRunner
from aegis.storage.trigger_store import TriggerStore


@pytest.fixture
def mock_store() -> TriggerStore:
    """Create a TriggerStore with a temp DB."""
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = TriggerStore(db_path=db_path)
    yield store
    os.unlink(db_path)


class TestTriggerCheckRunner:
    @pytest.mark.asyncio
    async def test_no_active_triggers_returns_empty(self, mock_store: TriggerStore) -> None:
        runner = TriggerCheckRunner(trigger_store=mock_store)
        fired = await runner.run()
        assert fired == []

    @pytest.mark.asyncio
    async def test_expired_trigger_is_marked_expired(self, mock_store: TriggerStore) -> None:
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        trigger_id = await mock_store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 475},
            "suggested_action": {},
            "valid_until": past,
        })

        runner = TriggerCheckRunner(trigger_store=mock_store)
        fired = await runner.run()
        assert fired == []

        result = await mock_store.get_trigger(trigger_id)
        assert result is not None
        assert result["status"] == "expired"

    @pytest.mark.asyncio
    async def test_price_below_trigger_fires(self, mock_store: TriggerStore) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        await mock_store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 475, "_current_price": 470},
            "suggested_action": {"action": "buy", "strategy": "leaps_call"},
            "valid_until": future,
        })

        runner = TriggerCheckRunner(trigger_store=mock_store)
        fired = await runner.run()
        assert len(fired) == 1
        assert fired[0]["ticker"] == "QQQ"

    @pytest.mark.asyncio
    async def test_price_below_trigger_does_not_fire_when_above(
        self, mock_store: TriggerStore
    ) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        await mock_store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 475, "_current_price": 480},
            "suggested_action": {},
            "valid_until": future,
        })

        runner = TriggerCheckRunner(trigger_store=mock_store)
        fired = await runner.run()
        assert fired == []

    @pytest.mark.asyncio
    async def test_price_above_trigger_fires(self, mock_store: TriggerStore) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        await mock_store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "price_above",
            "trigger_params": {"threshold": 500, "_current_price": 510},
            "suggested_action": {},
            "valid_until": future,
        })

        runner = TriggerCheckRunner(trigger_store=mock_store)
        fired = await runner.run()
        assert len(fired) == 1

    @pytest.mark.asyncio
    async def test_rsi_below_trigger_fires(self, mock_store: TriggerStore) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        await mock_store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "rsi_below",
            "trigger_params": {"threshold": 30, "_current_rsi": 25},
            "suggested_action": {},
            "valid_until": future,
        })

        runner = TriggerCheckRunner(trigger_store=mock_store)
        fired = await runner.run()
        assert len(fired) == 1

    @pytest.mark.asyncio
    async def test_volume_spike_trigger_fires(self, mock_store: TriggerStore) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        await mock_store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "volume_spike",
            "trigger_params": {
                "_current_volume": 50000000,
                "avg_volume": 20000000,
                "multiplier": 1.5,
            },
            "suggested_action": {},
            "valid_until": future,
        })

        runner = TriggerCheckRunner(trigger_store=mock_store)
        fired = await runner.run()
        assert len(fired) == 1

    @pytest.mark.asyncio
    async def test_volume_spike_below_threshold_does_not_fire(
        self, mock_store: TriggerStore
    ) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        await mock_store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "volume_spike",
            "trigger_params": {
                "_current_volume": 25000000,
                "avg_volume": 20000000,
                "multiplier": 1.5,
            },
            "suggested_action": {},
            "valid_until": future,
        })

        runner = TriggerCheckRunner(trigger_store=mock_store)
        fired = await runner.run()
        assert fired == []

    @pytest.mark.asyncio
    async def test_fired_trigger_not_in_active_list(self, mock_store: TriggerStore) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        await mock_store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 475, "_current_price": 470},
            "suggested_action": {},
            "valid_until": future,
        })

        runner = TriggerCheckRunner(trigger_store=mock_store)
        await runner.run()

        # Second run should not re-fire
        fired2 = await runner.run()
        assert fired2 == []

    @pytest.mark.asyncio
    async def test_sends_telegram_notification(self, mock_store: TriggerStore) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        await mock_store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 475, "_current_price": 470},
            "suggested_action": {"action": "buy", "strategy": "leaps_call"},
            "valid_until": future,
        })

        mock_telegram = AsyncMock()
        mock_telegram.send_message = AsyncMock()
        mock_telegram.send_trigger = AsyncMock()

        runner = TriggerCheckRunner(
            trigger_store=mock_store,
            telegram_notifier=mock_telegram,
        )
        fired = await runner.run()
        assert len(fired) == 1
        mock_telegram.send_trigger.assert_called_once()
