"""MemoryCleaner — cron-driven expired short-term memory deletion."""

from __future__ import annotations

from aegis.memory.short_term_store import ShortTermStore


class MemoryCleaner:
    """Deletes expired short-term memory records. Thin wrapper for cron jobs."""

    def __init__(self, short_term_store: ShortTermStore) -> None:
        self._short_term = short_term_store

    def run_cleanup(self) -> int:
        """Delete all expired short-term memory records.

        Returns:
            Number of deleted records.
        """
        return self._short_term.cleanup_expired()
