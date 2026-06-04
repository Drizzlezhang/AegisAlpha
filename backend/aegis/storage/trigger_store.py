"""TriggerStore — persist pending triggers to SQLite."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from aegis.utils.settings import settings


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    import json
    return {
        "id": row["id"],
        "ticker": row["ticker"],
        "trigger_type": row["trigger_type"],
        "trigger_params": json.loads(row["trigger_params"]),
        "suggested_action": json.loads(row["suggested_action"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "valid_until": row["valid_until"],
        "fired_at": row["fired_at"],
    }


class TriggerStore:
    """CRUD operations for pending triggers in pipeline.db."""

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            db_url = settings.DATABASE_URL
            db_path = db_url.replace("sqlite:///", "")
        self._db_path = Path(db_path)
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_triggers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    trigger_params TEXT NOT NULL DEFAULT '{}',
                    suggested_action TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    valid_until TEXT NOT NULL,
                    fired_at TEXT,
                    UNIQUE(ticker, trigger_type, status)
                )
            """)
            conn.commit()

    async def create_trigger(self, trigger: dict[str, Any]) -> int:
        """Create a new pending trigger. Returns the trigger ID."""

        import json

        def _create() -> int:
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO pending_triggers
                        (ticker, trigger_type, trigger_params, suggested_action,
                         status, valid_until)
                    VALUES (?, ?, ?, ?, 'pending', ?)
                    """,
                    (
                        trigger["ticker"],
                        trigger["trigger_type"],
                        json.dumps(trigger.get("trigger_params", {})),
                        json.dumps(trigger.get("suggested_action", {})),
                        trigger.get("valid_until", ""),
                    ),
                )
                conn.commit()
                return cursor.lastrowid or 0

        trigger_id = await asyncio.to_thread(_create)
        logger.info(f"TriggerStore: created trigger {trigger_id} for {trigger['ticker']}")
        return trigger_id

    async def list_active_triggers(self) -> list[dict[str, Any]]:
        """List all triggers with status='pending' and valid_until > now."""

        import json

        def _list() -> list[dict[str, Any]]:
            now = datetime.now(UTC).isoformat()
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT * FROM pending_triggers
                    WHERE status = 'pending' AND valid_until > ?
                    ORDER BY created_at ASC
                    """,
                    (now,),
                ).fetchall()
                return [_row_to_dict(row) for row in rows]

        return await asyncio.to_thread(_list)

    async def list_all_pending(self) -> list[dict[str, Any]]:
        """List all triggers with status='pending' (including expired ones)."""

        import json

        def _list() -> list[dict[str, Any]]:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT * FROM pending_triggers
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    """
                ).fetchall()
                return [_row_to_dict(row) for row in rows]

        return await asyncio.to_thread(_list)

    async def mark_triggered(self, trigger_id: int) -> None:
        """Mark a trigger as triggered."""

        def _mark() -> None:
            now = datetime.now(UTC).isoformat()
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    """
                    UPDATE pending_triggers
                    SET status = 'triggered', fired_at = ?
                    WHERE id = ?
                    """,
                    (now, trigger_id),
                )
                conn.commit()

        await asyncio.to_thread(_mark)
        logger.info(f"TriggerStore: trigger {trigger_id} marked as triggered")

    async def mark_expired(self, trigger_id: int) -> None:
        """Mark a trigger as expired."""

        def _mark() -> None:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    "UPDATE pending_triggers SET status = 'expired' WHERE id = ?",
                    (trigger_id,),
                )
                conn.commit()

        await asyncio.to_thread(_mark)
        logger.info(f"TriggerStore: trigger {trigger_id} marked as expired")

    async def cancel_trigger(self, trigger_id: int) -> None:
        """Cancel a trigger (set status to 'cancelled')."""

        def _cancel() -> None:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    "UPDATE pending_triggers SET status = 'cancelled' WHERE id = ?",
                    (trigger_id,),
                )
                conn.commit()

        await asyncio.to_thread(_cancel)
        logger.info(f"TriggerStore: trigger {trigger_id} cancelled")

    async def get_trigger(self, trigger_id: int) -> dict[str, Any] | None:
        """Get a single trigger by ID."""

        def _get() -> dict[str, Any] | None:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM pending_triggers WHERE id = ?",
                    (trigger_id,),
                ).fetchone()
                if row is None:
                    return None
                return _row_to_dict(row)

        return await asyncio.to_thread(_get)
