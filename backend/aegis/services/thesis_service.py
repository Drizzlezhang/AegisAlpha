"""ThesisService — Thesis Card lifecycle management.

Flow:
  Recommendation passes Risk Gate → user confirms → create_from_recommendation()
    → daily ThesisValidatorAgent checks → update_valid_status()
    → user closes → close_thesis() → Episodic Memory + WeightAdapter
    → 30 days later → check_re_entry()
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from aegis.memory.long_term_store import LongTermStore
from aegis.memory.service import MemoryService
from aegis.memory.weight_adapter import WeightAdapter
from aegis.storage.thesis_store import ThesisStore


class ThesisService:
    """Complete lifecycle management for Thesis Cards.

    Dependencies (all injected):
        thesis_store: CRUD on thesis_cards (AsyncSession)
        memory: MemoryService (for read/search/summarize)
        weight_adapter: WeightAdapter (sync, needs Session)
        long_term_store: LongTermStore (episodic memory writes)
        session_factory: Callable[[], Session] (for WeightAdapter sync calls)
    """

    def __init__(
        self,
        thesis_store: ThesisStore,
        memory: MemoryService,
        weight_adapter: WeightAdapter,
        long_term_store: LongTermStore,
        session_factory: Callable[[], Session],
    ) -> None:
        self._store = thesis_store
        self._memory = memory
        self._weight_adapter = weight_adapter
        self._long_term = long_term_store
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_from_recommendation(
        self,
        recommendation: dict[str, Any],
        weight_snapshot: dict[str, Any],
        user_confirmed: bool = True,
    ) -> int:
        """Auto-create a ThesisCard when a recommendation is executed.

        Args:
            recommendation: Pipeline output dict. Required keys:
                ticker, direction, entry_price, target_price, stop_price,
                key_assumptions, entry_mode.
            weight_snapshot: Current factor weights from state.weight_snapshot.
            user_confirmed: Whether the user confirmed execution.

        Returns:
            New thesis_card id.

        Raises:
            ValueError: If user_confirmed=False or active thesis exists for ticker.
        """
        if not user_confirmed:
            raise ValueError("User must confirm before creating thesis")

        ticker = recommendation["ticker"]

        # Cooldown check: no duplicate active thesis for same ticker
        active = await self._store.get_active(ticker=ticker)
        if active:
            raise ValueError(
                f"Active thesis already exists for {ticker} (id={active[0].id}). "
                "Close existing thesis before creating new one."
            )

        card_data = {
            "ticker": ticker,
            "direction": recommendation["direction"],
            "entry_mode": recommendation.get("entry_mode", "active_right"),
            "entry_date": datetime.now(UTC),
            "entry_price": recommendation["entry_price"],
            "target_price": recommendation.get("target_price"),
            "stop_price": recommendation.get("stop_price"),
            "key_assumptions": recommendation.get("key_assumptions", []),
            "thesis_valid_status": "valid",
            "re_entry_flagged": False,
            "factor_snapshot": weight_snapshot,
        }

        thesis_id = await self._store.create(card_data)
        logger.info(f"Thesis {thesis_id} created for {ticker} ({recommendation['direction']})")
        return thesis_id

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    async def close_thesis(
        self,
        thesis_id: int,
        close_price: float,
        judgment_score: int,
        execution_score: int,
        close_reason: str = "",
    ) -> dict[str, Any]:
        """Close a thesis position with dual-dimension scoring.

        1. Validate scores (1-5)
        2. Compute P&L by direction
        3. Update thesis_cards table
        4. Write episodic memory (best-effort)
        5. Trigger WeightAdapter recalculation

        Args:
            thesis_id: ThesisCard ID.
            close_price: Closing price.
            judgment_score: System judgment score 1-5.
            execution_score: User execution score 1-5.
            close_reason: stop_hit / target_reached / thesis_broken / manual.

        Returns:
            Dict with thesis_id, pnl_pct, new_weights.
        """
        if not 1 <= judgment_score <= 5:
            raise ValueError("judgment_score must be 1-5")
        if not 1 <= execution_score <= 5:
            raise ValueError("execution_score must be 1-5")

        card = await self._store.get_by_id(thesis_id)
        if card is None:
            raise ValueError(f"Thesis {thesis_id} not found")
        if card.close_date is not None:
            raise ValueError(f"Thesis {thesis_id} already closed")

        # Compute P&L
        pnl_pct = self._compute_pnl(card.direction, card.entry_price, close_price)

        close_data = {
            "close_date": datetime.now(UTC),
            "close_price": close_price,
            "actual_pnl_pct": pnl_pct,
            "judgment_score": judgment_score,
            "execution_score": execution_score,
            "close_reason": close_reason,
        }

        await self._store.close(thesis_id, close_data)
        logger.info(
            f"Thesis {thesis_id} closed: PnL={pnl_pct:.2%}, "
            f"J={judgment_score}, E={execution_score}, reason={close_reason}"
        )

        # Write episodic memory (best-effort, non-blocking)
        await self._write_episodic_memory(card, close_price, pnl_pct, judgment_score, execution_score, close_reason)

        # Trigger WeightAdapter (sync, run in thread)
        new_weights: dict[str, float] = {}
        try:
            new_weights = await asyncio.to_thread(self._run_weight_update)
            logger.info(f"WeightAdapter updated: {len(new_weights)} factors changed")
        except Exception:
            logger.exception("WeightAdapter update failed (non-blocking)")

        return {
            "thesis_id": thesis_id,
            "pnl_pct": pnl_pct,
            "new_weights": new_weights,
        }

    # ------------------------------------------------------------------
    # Validation status
    # ------------------------------------------------------------------

    async def update_valid_status(
        self,
        thesis_id: int,
        new_status: str,
        broken_assumptions: list[str] | None = None,
    ) -> None:
        """Update thesis_valid_status. Called by ThesisValidatorAgent.

        Status transitions (one-way only):
            valid → partial_broken → fully_broken
            valid → fully_broken (direct)
            No rollback allowed.

        Args:
            thesis_id: ThesisCard ID.
            new_status: "valid" / "partial_broken" / "fully_broken".
            broken_assumptions: List of assumption strings that are broken.
        """
        valid_statuses = {"valid", "partial_broken", "fully_broken"}
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}")

        card = await self._store.get_by_id(thesis_id)
        if card is None:
            raise ValueError(f"Thesis {thesis_id} not found")
        if card.close_date is not None:
            return  # Already closed, skip

        # One-way: never roll back
        status_order = {"valid": 0, "partial_broken": 1, "fully_broken": 2}
        current_order = status_order.get(card.thesis_valid_status, 0)
        new_order = status_order.get(new_status, 0)
        if new_order < current_order:
            logger.debug(
                f"Thesis {thesis_id}: ignoring rollback {card.thesis_valid_status} → {new_status}"
            )
            return

        update_data: dict[str, Any] = {"thesis_valid_status": new_status}
        if broken_assumptions:
            existing: list[str] = list(card.key_assumptions) if card.key_assumptions else []
            marked: list[str] = []
            for assumption in existing:
                if assumption in broken_assumptions:
                    marked.append(f"[BROKEN] {assumption}")
                else:
                    marked.append(assumption)
            update_data["key_assumptions"] = marked

        await self._store.update(thesis_id, update_data)
        logger.info(
            f"Thesis {thesis_id}: status {card.thesis_valid_status} → {new_status}"
        )

    # ------------------------------------------------------------------
    # Re-entry check
    # ------------------------------------------------------------------

    async def check_re_entry(self, ticker: str) -> bool:
        """Check if a ticker should be flagged for re-entry.

        Conditions:
        1. Has a closed thesis for this ticker
        2. Closed ≥ 30 days ago
        3. judgment_score ≥ 3
        4. No active thesis for this ticker

        Returns:
            True if re_entry_flagged was set.
        """
        active = await self._store.get_active(ticker=ticker)
        if active:
            return False

        recently_closed = await self._store.get_recently_closed(ticker, days=90)
        for card in recently_closed:
            if card.close_date is None:
                continue
            days_since_close = (date.today() - card.close_date.date()).days
            if days_since_close >= 30 and (card.judgment_score or 0) >= 3:
                await self._store.update(card.id, {"re_entry_flagged": True})
                logger.info(f"Thesis {card.id}: re_entry_flagged for {ticker}")
                return True

        return False

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_active_theses(self, ticker: str | None = None) -> list[dict[str, Any]]:
        """Get all active (unclosed) ThesisCards."""
        cards = await self._store.get_active(ticker=ticker)
        return [self._card_to_dict(c) for c in cards]

    async def get_closed_with_scores(self) -> list[dict[str, Any]]:
        """Get closed ThesisCards with dual scores (for WeightAdapter)."""
        return await self._store.get_closed_with_scores()

    async def has_active_thesis(self, ticker: str) -> bool:
        """Cooldown check: does an active thesis exist for this ticker?"""
        active = await self._store.get_active(ticker=ticker)
        return len(active) > 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_pnl(direction: str, entry_price: float, close_price: float) -> float:
        """Compute P&L percentage based on direction.

        long: (close - entry) / entry
        short_put / cc: (entry - close) / entry (premium collected)
        """
        if direction in ("short_put", "cc"):
            return (entry_price - close_price) / entry_price
        return (close_price - entry_price) / entry_price

    async def _write_episodic_memory(
        self,
        card: Any,
        close_price: float,
        pnl_pct: float,
        judgment_score: int,
        execution_score: int,
        close_reason: str,
    ) -> None:
        """Write closed thesis data to episodic memory via LongTermStore.

        Best-effort: failures are logged but do not block close_thesis.
        """
        try:
            holding_days = (
                datetime.now(UTC) - card.entry_date.replace(tzinfo=UTC)
            ).days

            content = {
                "thesis_id": card.id,
                "ticker": card.ticker,
                "direction": card.direction,
                "entry_date": card.entry_date.isoformat() if card.entry_date else None,
                "entry_price": card.entry_price,
                "close_price": close_price,
                "actual_pnl_pct": pnl_pct,
                "judgment_score": judgment_score,
                "execution_score": execution_score,
                "close_reason": close_reason,
                "factor_snapshot": card.factor_snapshot,
                "key_assumptions": card.key_assumptions,
                "holding_days": holding_days,
            }

            await asyncio.to_thread(
                self._long_term.insert,
                {
                    "ticker": card.ticker,
                    "data_type": "episodic_thesis",
                    "content": content,
                    "original_date": datetime.now(UTC),
                },
            )
            logger.debug(f"Episodic memory written for thesis {card.id}")
        except Exception:
            logger.exception(f"Episodic memory write failed for thesis {card.id} (non-blocking)")

    def _run_weight_update(self) -> dict[str, float]:
        """Run WeightAdapter.update_weights in a sync Session context."""
        session = self._session_factory()
        try:
            return self._weight_adapter.update_weights(session)
        finally:
            session.close()

    @staticmethod
    def _card_to_dict(card: Any) -> dict[str, Any]:
        """Convert a ThesisCard ORM object to a dict."""
        return {
            "id": card.id,
            "ticker": card.ticker,
            "direction": card.direction,
            "entry_mode": card.entry_mode,
            "entry_date": card.entry_date.isoformat() if card.entry_date else None,
            "entry_price": card.entry_price,
            "target_price": card.target_price,
            "stop_price": card.stop_price,
            "key_assumptions": card.key_assumptions,
            "thesis_valid_status": card.thesis_valid_status,
            "re_entry_flagged": card.re_entry_flagged,
            "factor_snapshot": card.factor_snapshot,
            "close_date": card.close_date.isoformat() if card.close_date else None,
            "close_price": card.close_price,
            "actual_pnl_pct": card.actual_pnl_pct,
            "judgment_score": card.judgment_score,
            "execution_score": card.execution_score,
            "close_reason": card.close_reason,
            "created_at": card.created_at.isoformat() if card.created_at else None,
        }
