"""Tests for MemoryCleaner."""

from unittest.mock import MagicMock

from aegis.memory.cleaner import MemoryCleaner


class TestRunCleanup:
    def test_delegates_to_short_term_store(self):
        mock_store = MagicMock()
        mock_store.cleanup_expired.return_value = 5
        cleaner = MemoryCleaner(mock_store)
        result = cleaner.run_cleanup()
        assert result == 5
        mock_store.cleanup_expired.assert_called_once()
