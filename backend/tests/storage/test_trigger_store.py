"""Tests for TriggerStore — CRUD operations for pending triggers."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta

import pytest

from aegis.storage.trigger_store import TriggerStore


@pytest.fixture
def store() -> TriggerStore:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = TriggerStore(db_path=db_path)
    yield store
    import os
    os.unlink(db_path)


class TestTriggerStore:
    @pytest.mark.asyncio
    async def test_create_and_get_trigger(self, store: TriggerStore) -> None:
        trigger = {
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 475},
            "suggested_action": {"action": "buy", "strategy": "leaps_call"},
            "valid_until": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        }
        trigger_id = await store.create_trigger(trigger)
        assert trigger_id > 0

        result = await store.get_trigger(trigger_id)
        assert result is not None
        assert result["ticker"] == "QQQ"
        assert result["trigger_type"] == "price_below"
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_active_triggers(self, store: TriggerStore) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        await store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 475},
            "suggested_action": {},
            "valid_until": future,
        })
        await store.create_trigger({
            "ticker": "SPY",
            "trigger_type": "price_above",
            "trigger_params": {"threshold": 600},
            "suggested_action": {},
            "valid_until": future,
        })

        active = await store.list_active_triggers()
        assert len(active) == 2

    @pytest.mark.asyncio
    async def test_list_excludes_expired(self, store: TriggerStore) -> None:
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        await store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 475},
            "suggested_action": {},
            "valid_until": past,
        })
        await store.create_trigger({
            "ticker": "SPY",
            "trigger_type": "price_above",
            "trigger_params": {"threshold": 600},
            "suggested_action": {},
            "valid_until": future,
        })

        active = await store.list_active_triggers()
        assert len(active) == 1
        assert active[0]["ticker"] == "SPY"

    @pytest.mark.asyncio
    async def test_mark_triggered(self, store: TriggerStore) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        trigger_id = await store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 475},
            "suggested_action": {},
            "valid_until": future,
        })

        await store.mark_triggered(trigger_id)
        result = await store.get_trigger(trigger_id)
        assert result is not None
        assert result["status"] == "triggered"
        assert result["fired_at"] is not None

    @pytest.mark.asyncio
    async def test_mark_expired(self, store: TriggerStore) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        trigger_id = await store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 475},
            "suggested_action": {},
            "valid_until": future,
        })

        await store.mark_expired(trigger_id)
        result = await store.get_trigger(trigger_id)
        assert result is not None
        assert result["status"] == "expired"

    @pytest.mark.asyncio
    async def test_cancel_trigger(self, store: TriggerStore) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        trigger_id = await store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 475},
            "suggested_action": {},
            "valid_until": future,
        })

        await store.cancel_trigger(trigger_id)
        result = await store.get_trigger(trigger_id)
        assert result is not None
        assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_get_nonexistent_trigger(self, store: TriggerStore) -> None:
        result = await store.get_trigger(99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_triggered_not_in_active_list(self, store: TriggerStore) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        trigger_id = await store.create_trigger({
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "trigger_params": {"threshold": 475},
            "suggested_action": {},
            "valid_until": future,
        })

        await store.mark_triggered(trigger_id)
        active = await store.list_active_triggers()
        assert len(active) == 0
