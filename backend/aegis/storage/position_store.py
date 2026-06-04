"""PositionStore — persist broker positions to SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

from aegis.tools.brokers.base import BrokerPosition
from aegis.utils.settings import settings


class PositionStore:
    """Batch upsert broker positions to SQLite positions table."""

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            db_url = settings.DATABASE_URL
            # sqlite:///./data/aegis.db → ./data/aegis.db
            db_path = db_url.replace("sqlite:///", "")
        self._db_path = Path(db_path)
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    pos_type TEXT NOT NULL DEFAULT 'stock',
                    quantity INTEGER NOT NULL DEFAULT 0,
                    avg_cost REAL NOT NULL DEFAULT 0.0,
                    current_price REAL,
                    strike REAL,
                    expiry TEXT,
                    option_type TEXT,
                    delta REAL,
                    gamma REAL,
                    theta REAL,
                    vega REAL,
                    iv REAL,
                    delta_dollars REAL,
                    unrealized_pnl REAL,
                    entry_mode TEXT,
                    grade TEXT,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(account, ticker, pos_type)
                )
            """)
            conn.commit()

    async def upsert_positions(self, positions: list[BrokerPosition]) -> None:
        """Batch upsert positions into the positions table."""
        if not positions:
            return

        import asyncio

        def _upsert() -> None:
            with sqlite3.connect(str(self._db_path)) as conn:
                for pos in positions:
                    conn.execute(
                        """
                        INSERT INTO positions
                            (account, ticker, pos_type, quantity, avg_cost,
                             current_price, strike, expiry, option_type,
                             delta, gamma, theta, vega, iv,
                             delta_dollars, unrealized_pnl, entry_mode, grade)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(account, ticker, pos_type)
                        DO UPDATE SET
                            quantity = excluded.quantity,
                            avg_cost = excluded.avg_cost,
                            current_price = excluded.current_price,
                            delta = excluded.delta,
                            gamma = excluded.gamma,
                            theta = excluded.theta,
                            vega = excluded.vega,
                            iv = excluded.iv,
                            delta_dollars = excluded.delta_dollars,
                            unrealized_pnl = excluded.unrealized_pnl,
                            entry_mode = excluded.entry_mode,
                            grade = excluded.grade,
                            updated_at = datetime('now')
                        """,
                        (
                            pos.account, pos.ticker, pos.pos_type,
                            pos.quantity, pos.avg_cost,
                            pos.current_price, pos.strike, pos.expiry,
                            pos.option_type, pos.delta, pos.gamma,
                            pos.theta, pos.vega, pos.iv,
                            pos.delta_dollars, pos.unrealized_pnl,
                            pos.entry_mode, pos.grade,
                        ),
                    )
                conn.commit()

        await asyncio.to_thread(_upsert)
        logger.info(f"PositionStore: upserted {len(positions)} positions")
