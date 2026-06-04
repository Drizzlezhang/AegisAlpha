"""Unit tests for TelegramNotifier — formatting, splitting, edge cases."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.notifier.telegram import TelegramNotifier
from aegis.pipeline.state import (
    BlockedRecommendation,
    PipelineState,
    Recommendation,
)


def _make_recommendation(
    action: str = "buy",
    ticker: str = "QQQ",
    strategy: str = "LEAPS Call",
    score: float = 85.0,
) -> Recommendation:
    return Recommendation(
        ticker=ticker,
        action=action,  # type: ignore[arg-type]
        strategy=strategy,
        rationale="Test rationale for the recommendation.",
        urgency="high",
        score=score,
        delta_dollars_delta=5000.0,
    )


def _make_blocked(rec: Recommendation, reason: str = "VIX > 30") -> BlockedRecommendation:
    return BlockedRecommendation(recommendation=rec, block_reason=reason)


class TestTelegramNotifierFormatting:
    """Test message formatting with templates."""

    def test_format_recommendation_buy(self) -> None:
        """Buy recommendation should use 📊 prefix."""
        notifier = TelegramNotifier()
        rec = _make_recommendation(action="buy")
        msg = notifier._format_recommendation(rec)
        assert "📊" in msg
        assert "QQQ" in msg
        assert "BUY" in msg
        assert "LEAPS Call" in msg

    def test_format_recommendation_sell(self) -> None:
        """Sell recommendation should use ⚙️ prefix."""
        notifier = TelegramNotifier()
        rec = _make_recommendation(action="sell")
        msg = notifier._format_recommendation(rec)
        assert "⚙️" in msg
        assert "SELL" in msg

    def test_format_recommendation_hold(self) -> None:
        """Hold recommendation should use ℹ️ prefix."""
        notifier = TelegramNotifier()
        rec = _make_recommendation(action="hold")
        msg = notifier._format_recommendation(rec)
        assert "ℹ️" in msg

    def test_format_blocked(self) -> None:
        """Blocked recommendation should show reason."""
        notifier = TelegramNotifier()
        rec = _make_recommendation()
        blocked = _make_blocked(rec, "VIX > 30")
        msg = notifier._format_blocked(blocked)
        assert "⚠️" in msg
        assert "VIX > 30" in msg

    def test_format_errors(self) -> None:
        """Error formatting should list all errors."""
        notifier = TelegramNotifier()
        errors = [
            {"agent": "debate_agent", "error": "LLM timeout"},
            {"agent": "data_harvester", "error": "API rate limit"},
        ]
        msg = notifier._format_errors(errors)
        assert "❗" in msg
        assert "debate_agent" in msg
        assert "LLM timeout" in msg
        assert "data_harvester" in msg


class TestTelegramNotifierSplitting:
    """Test 4000-character message splitting."""

    def test_split_short_message(self) -> None:
        """Short message should not be split."""
        text = "Hello, this is a short message."
        chunks = TelegramNotifier._split_text(text, 4000)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_long_message(self) -> None:
        """Long message should be split into chunks ≤ max_len."""
        text = "A" * 5000
        chunks = TelegramNotifier._split_text(text, 4000)
        assert len(chunks) == 2
        assert all(len(c) <= 4000 for c in chunks)

    def test_split_at_newline(self) -> None:
        """Split should prefer newline boundaries."""
        line1 = "A" * 100 + "\n"
        line2 = "B" * 3900 + "\n"
        line3 = "C" * 100
        text = line1 + line2 + line3
        chunks = TelegramNotifier._split_text(text, 4000)
        assert all(len(c) <= 4000 for c in chunks)
        # First chunk should end at a newline if possible
        assert chunks[0].endswith("A" * 100)

    def test_split_exact_boundary(self) -> None:
        """Message exactly at boundary should not be split."""
        text = "X" * 4000
        chunks = TelegramNotifier._split_text(text, 4000)
        assert len(chunks) == 1

    def test_split_empty(self) -> None:
        """Empty string should return empty list."""
        chunks = TelegramNotifier._split_text("", 4000)
        assert chunks == []


class TestTelegramNotifierSend:
    """Test send behavior with mocked bot."""

    @pytest.mark.asyncio
    async def test_send_full_pipeline(self) -> None:
        """Send full pipeline results."""
        notifier = TelegramNotifier()
        rec = _make_recommendation()
        state = PipelineState(
            pipeline_id="test-001",
            pipeline_mode="full",
            recommendations=[rec],
        )

        with patch.object(notifier, "_send_message", new_callable=AsyncMock) as mock_send:
            await notifier._send_full(state)
            assert mock_send.call_count >= 1

    @pytest.mark.asyncio
    async def test_send_lightweight_pipeline(self) -> None:
        """Send lightweight pipeline results."""
        notifier = TelegramNotifier()
        state = PipelineState(
            pipeline_id="test-002",
            pipeline_mode="lightweight",
            health_scores={"QQQ": 95.5},
            passive_health_alerts=[
                {
                    "ticker": "QQQ",
                    "type": "price_deviation",
                    "pct_change": 0.05,
                    "severity": "warning",
                }
            ],
        )

        with patch.object(notifier, "_send_message", new_callable=AsyncMock) as mock_send:
            await notifier._send_lightweight(state)
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_dispatches_to_lightweight(self) -> None:
        """send() should dispatch to _send_lightweight for lightweight mode."""
        notifier = TelegramNotifier()
        state = PipelineState(pipeline_id="test-003", pipeline_mode="lightweight")

        with (
            patch.object(notifier, "_send_lightweight", new_callable=AsyncMock) as mock_lw,
            patch.object(notifier, "_send_full", new_callable=AsyncMock) as mock_full,
        ):
            await notifier.send(state)
            mock_lw.assert_called_once()
            mock_full.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_dispatches_to_full(self) -> None:
        """send() should dispatch to _send_full for full mode."""
        notifier = TelegramNotifier()
        state = PipelineState(pipeline_id="test-004", pipeline_mode="full")

        with (
            patch.object(notifier, "_send_lightweight", new_callable=AsyncMock) as mock_lw,
            patch.object(notifier, "_send_full", new_callable=AsyncMock) as mock_full,
        ):
            await notifier.send(state)
            mock_full.assert_called_once()
            mock_lw.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_message_adds_beta_prefix(self) -> None:
        """All messages should have 🧪 [Beta] prefix (AC-4)."""
        notifier = TelegramNotifier()

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        notifier._bot = mock_bot

        with (
            patch.object(notifier, "_get_bot", return_value=mock_bot),
            patch("aegis.notifier.telegram.settings") as mock_settings,
        ):
            mock_settings.TELEGRAM_CHAT_ID = "12345"
            await notifier._send_message("Test message")
            call_args = mock_bot.send_message.call_args
            assert "🧪 [Beta]" in call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_send_message_missing_token(self) -> None:
        """Missing TELEGRAM_BOT_TOKEN should skip push (Edge-2)."""
        notifier = TelegramNotifier()

        with patch.object(notifier, "_get_bot", return_value=None):
            # Should not raise
            await notifier._send_message("Test message")

    @pytest.mark.asyncio
    async def test_send_message_missing_chat_id(self) -> None:
        """Missing TELEGRAM_CHAT_ID should skip push."""
        notifier = TelegramNotifier()

        mock_bot = MagicMock()
        notifier._bot = mock_bot

        with (
            patch.object(notifier, "_get_bot", return_value=mock_bot),
            patch("aegis.notifier.telegram.settings") as mock_settings,
        ):
            mock_settings.TELEGRAM_CHAT_ID = ""
            await notifier._send_message("Test message")
            mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_trigger_notification(self) -> None:
        """send_trigger() should format and send trigger notification."""
        notifier = TelegramNotifier()
        trigger = {
            "ticker": "QQQ",
            "trigger_type": "price_below",
            "suggested_action": {"action": "buy", "strategy": "leaps_call"},
            "trigger_params": {"threshold": 475},
        }

        with patch.object(notifier, "_send_message", new_callable=AsyncMock) as mock_send:
            await notifier.send_trigger(trigger)
            mock_send.assert_called_once()
            msg = mock_send.call_args[0][0]
            assert "⏰" in msg
            assert "QQQ" in msg
            assert "price_below" in msg
            assert "buy" in msg
            assert "leaps_call" in msg
