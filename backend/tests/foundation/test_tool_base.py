"""Test BaseTool + ToolResult contract."""

from aegis.tools.base import ToolResult


class TestToolResult:
    """Verify ToolResult field completeness."""

    def test_all_fields_exist(self) -> None:
        """ToolResult should have success, data, error, source, cached."""
        tr = ToolResult(success=True)
        assert tr.success is True
        assert tr.data is None
        assert tr.error is None
        assert tr.source == ""
        assert tr.cached is False

    def test_error_case(self) -> None:
        """ToolResult should capture error info."""
        tr = ToolResult(success=False, error="Connection timeout", source="yfinance")
        assert tr.success is False
        assert tr.error == "Connection timeout"
        assert tr.source == "yfinance"

    def test_cached_flag(self) -> None:
        """ToolResult should track cached status."""
        tr = ToolResult(success=True, data={"price": 100.0}, cached=True)
        assert tr.cached is True
        assert tr.data == {"price": 100.0}
