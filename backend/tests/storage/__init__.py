"""Tests for PositionStore — upsert and dedup."""

import asyncio
import os
import tempfile

import pytest

from aegis.storage.position_store import PositionStore
from aegis.tools.brokers.base import BrokerPosition


class TestPositionStore:
    """AC-8: PositionStore CRUD and dedup."""

    @pytest.fixture
    def store(self) -> PositionStore:
        db = tempfile.mktemp(suffix=".db")
        store = PositionStore(db_path=db)
        yield store
        if os.path.exists(db):
            os.unlink(db)

    def test_upsert_single_position(self, store: PositionStore) -> None:
        pos = BrokerPosition(
            account="futu", ticker="QQQ", pos_type="stock",
            quantity=100, avg_cost=350.0, entry_mode="active_left", grade="active",
        )
        asyncio.run(store.upsert_positions([pos]))

        import sqlite3
        conn = sqlite3.connect(str(store._db_path))
        rows = conn.execute("SELECT * FROM positions").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][2] == "QQQ"  # ticker
        assert rows[0][17] == "active_left"  # entry_mode
        assert rows[0][18] == "active"  # grade

    def test_upsert_dedup(self, store: PositionStore) -> None:
        """Same account+ticker+pos_type should update, not duplicate."""
        pos1 = BrokerPosition(account="futu", ticker="QQQ", pos_type="stock", quantity=100, avg_cost=350.0)
        pos2 = BrokerPosition(account="futu", ticker="QQQ", pos_type="stock", quantity=150, avg_cost=355.0)
        asyncio.run(store.upsert_positions([pos1]))
        asyncio.run(store.upsert_positions([pos2]))

        import sqlite3
        conn = sqlite3.connect(str(store._db_path))
        rows = conn.execute("SELECT * FROM positions").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][4] == 150  # quantity updated

    def test_upsert_empty_list(self, store: PositionStore) -> None:
        """Empty list should not crash."""
        asyncio.run(store.upsert_positions([]))
        import sqlite3
        conn = sqlite3.connect(str(store._db_path))
        rows = conn.execute("SELECT * FROM positions").fetchall()
        conn.close()
        assert len(rows) == 0

    def test_entry_mode_and_grade_persisted(self, store: PositionStore) -> None:
        pos = BrokerPosition(
            account="futu", ticker="SPY", pos_type="stock",
            quantity=50, avg_cost=450.0, entry_mode="passive", grade="passive",
        )
        asyncio.run(store.upsert_positions([pos]))

        import sqlite3
        conn = sqlite3.connect(str(store._db_path))
        row = conn.execute("SELECT entry_mode, grade FROM positions").fetchone()
        conn.close()
        assert row[0] == "passive"
        assert row[1] == "passive"
