"""Test MemoryInterface contract — 5 abstract methods."""
import inspect

from aegis.memory.interface import MemoryInterface


class TestMemoryInterface:
    """Verify MemoryInterface abstract contract."""

    def test_abstract_methods_count(self) -> None:
        """MemoryInterface should have exactly 5 abstract methods."""
        abstract_methods = MemoryInterface.__abstractmethods__
        assert len(abstract_methods) == 5

    def test_read_signature(self) -> None:
        """read(scope, query) -> list[dict]."""
        sig = inspect.signature(MemoryInterface.read)
        params = list(sig.parameters.keys())
        assert "scope" in params
        assert "query" in params

    def test_write_signature(self) -> None:
        """write(scope, data) -> None."""
        sig = inspect.signature(MemoryInterface.write)
        params = list(sig.parameters.keys())
        assert "scope" in params
        assert "data" in params

    def test_search_signature(self) -> None:
        """search(query, top_k=5) -> list[dict]."""
        sig = inspect.signature(MemoryInterface.search)
        params = list(sig.parameters.keys())
        assert "query" in params
        assert "top_k" in params

    def test_summarize_signature(self) -> None:
        """summarize(ticker, date_range) -> dict."""
        sig = inspect.signature(MemoryInterface.summarize)
        params = list(sig.parameters.keys())
        assert "ticker" in params
        assert "date_range" in params

    def test_archive_scratchpad_signature(self) -> None:
        """archive_scratchpad(pipeline_id, scratchpad) -> None."""
        sig = inspect.signature(MemoryInterface.archive_scratchpad)
        params = list(sig.parameters.keys())
        assert "pipeline_id" in params
        assert "scratchpad" in params
