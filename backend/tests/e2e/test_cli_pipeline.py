"""E2E tests for CLI — verify commands invoke correct runner/notifier functions."""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from aegis.cli import app

cli_runner = CliRunner()


def _run_in_new_loop(coro):
    """Run a coroutine in a fresh event loop (works even when a loop is already running)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestCliRun:
    """E2E tests for `aegis run` command."""

    def test_run_help(self) -> None:
        """`aegis run --help` should show options."""
        result = cli_runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--ticker" in result.stdout
        assert "--mode" in result.stdout

    def test_run_full_pre_market(self) -> None:
        """`aegis run --mode pre-market` should invoke run_full."""
        mock_state = MagicMock()
        mock_state.pipeline_id = "test-001"
        mock_state.error_flags = []

        mock_runner = MagicMock()
        mock_runner.run_full = AsyncMock(return_value=mock_state)
        mock_runner.run_lightweight = AsyncMock()

        with (
            patch.dict(sys.modules, {"aegis.pipeline.runner": mock_runner}),
            patch(
                "aegis.notifier.telegram.TelegramNotifier.send", new_callable=AsyncMock
            ) as mock_send,
            patch("asyncio.run", new=_run_in_new_loop),
        ):
            result = cli_runner.invoke(app, ["run", "--ticker", "QQQ", "--mode", "pre-market"])

            assert result.exit_code == 0
            mock_runner.run_full.assert_called_once()
            mock_send.assert_called_once()

    def test_run_lightweight(self) -> None:
        """`aegis run --mode lightweight` should invoke run_lightweight."""
        mock_state = MagicMock()
        mock_state.pipeline_id = "test-002"
        mock_state.error_flags = []

        mock_runner = MagicMock()
        mock_runner.run_full = AsyncMock()
        mock_runner.run_lightweight = AsyncMock(return_value=mock_state)

        with (
            patch.dict(sys.modules, {"aegis.pipeline.runner": mock_runner}),
            patch(
                "aegis.notifier.telegram.TelegramNotifier.send", new_callable=AsyncMock
            ) as mock_send,
            patch("asyncio.run", new=_run_in_new_loop),
        ):
            result = cli_runner.invoke(app, ["run", "--ticker", "QQQ", "--mode", "lightweight"])

            assert result.exit_code == 0
            mock_runner.run_lightweight.assert_called_once_with(["QQQ"])
            mock_send.assert_called_once()

    def test_run_post_market(self) -> None:
        """`aegis run --mode post-market` should invoke run_full with post-market."""
        mock_state = MagicMock()
        mock_state.pipeline_id = "test-003"
        mock_state.error_flags = []

        mock_runner = MagicMock()
        mock_runner.run_full = AsyncMock(return_value=mock_state)
        mock_runner.run_lightweight = AsyncMock()

        with (
            patch.dict(sys.modules, {"aegis.pipeline.runner": mock_runner}),
            patch(
                "aegis.notifier.telegram.TelegramNotifier.send", new_callable=AsyncMock
            ) as mock_send,
            patch("asyncio.run", new=_run_in_new_loop),
        ):
            result = cli_runner.invoke(app, ["run", "--ticker", "QQQ", "--mode", "post-market"])

            assert result.exit_code == 0
            mock_runner.run_full.assert_called_once()
            mock_send.assert_called_once()


class TestCliScheduleStart:
    """E2E tests for `aegis schedule start` command."""

    def test_schedule_start_missing_file(self) -> None:
        """Should error when schedule.yaml is missing."""
        with patch("aegis.cli.Path.exists", return_value=False):
            result = cli_runner.invoke(app, ["schedule-start"])
            assert result.exit_code == 1
            assert "not found" in result.stderr


class TestCliHealth:
    """E2E tests for `aegis health` command."""

    def test_health_runs(self) -> None:
        """`aegis health` should run and show status."""
        result = cli_runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "Health Check" in result.stdout


class TestCliVersion:
    """E2E tests for `aegis version` command."""

    def test_version(self) -> None:
        """`aegis version` should show version."""
        result = cli_runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "Aegis" in result.stdout
