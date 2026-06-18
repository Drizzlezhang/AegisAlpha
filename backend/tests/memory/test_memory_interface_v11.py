"""Test MemoryInterface v1.1 contract — extended signatures."""

import inspect

from aegis.memory.interface import MemoryInterface


class TestMemoryInterfaceV11:
    """Verify MemoryInterface v1.1 abstract contract."""

    def test_abstract_methods_count(self) -> None:
        """MemoryInterface should have exactly 5 abstract methods."""
        abstract_methods = MemoryInterface.__abstractmethods__
        assert len(abstract_methods) == 5

    def test_read_has_limit_param(self) -> None:
        """read() should have limit parameter with default 10."""
        sig = inspect.signature(MemoryInterface.read)
        params = sig.parameters
        assert "limit" in params
        assert params["limit"].default == 10

    def test_write_has_ttl_days_param(self) -> None:
        """write() should have ttl_days parameter with default None."""
        sig = inspect.signature(MemoryInterface.write)
        params = sig.parameters
        assert "ttl_days" in params
        assert params["ttl_days"].default is None

    def test_search_has_collection_and_filter(self) -> None:
        """search() should have collection and filter parameters."""
        sig = inspect.signature(MemoryInterface.search)
        params = sig.parameters
        assert "collection" in params
        assert params["collection"].default == "default"
        assert "filter" in params
        assert params["filter"].default is None

    def test_summarize_ticker_optional(self) -> None:
        """summarize() ticker should accept None."""
        sig = inspect.signature(MemoryInterface.summarize)
        params = sig.parameters
        assert "ticker" in params
        # ticker is str | None, default is inspect.Parameter.empty (no default)
        # but the type annotation allows None

    def test_summarize_has_data_type(self) -> None:
        """summarize() should have data_type parameter with default ''."""
        sig = inspect.signature(MemoryInterface.summarize)
        params = sig.parameters
        assert "data_type" in params
        assert params["data_type"].default == ""

    def test_backward_compatible_read(self) -> None:
        """read() still has scope and query params."""
        sig = inspect.signature(MemoryInterface.read)
        params = list(sig.parameters.keys())
        assert "scope" in params
        assert "query" in params

    def test_backward_compatible_write(self) -> None:
        """write() still has scope and data params."""
        sig = inspect.signature(MemoryInterface.write)
        params = list(sig.parameters.keys())
        assert "scope" in params
        assert "data" in params

    def test_backward_compatible_search(self) -> None:
        """search() still has query and top_k params."""
        sig = inspect.signature(MemoryInterface.search)
        params = list(sig.parameters.keys())
        assert "query" in params
        assert "top_k" in params

    def test_backward_compatible_summarize(self) -> None:
        """summarize() still has date_range param."""
        sig = inspect.signature(MemoryInterface.summarize)
        params = list(sig.parameters.keys())
        assert "date_range" in params

    def test_archive_scratchpad_unchanged(self) -> None:
        """archive_scratchpad() signature unchanged."""
        sig = inspect.signature(MemoryInterface.archive_scratchpad)
        params = list(sig.parameters.keys())
        assert "pipeline_id" in params
        assert "scratchpad" in params
