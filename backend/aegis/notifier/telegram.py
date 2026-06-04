"""Telegram Notifier — push pipeline results via Telegram Bot API.

Messages are formatted from config/prompts/telegram_*.j2 templates.
Supports 4000-char splitting, emoji prefixes, and graceful degradation
when TELEGRAM_BOT_TOKEN is not configured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from loguru import logger
from telegram import Bot
from telegram.error import TelegramError

from aegis.pipeline.state import PipelineState
from aegis.utils.settings import settings

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prompts"


class TelegramNotifier:
    """Send formatted pipeline results to Telegram.

    Templates:
        telegram_recommendation.j2 — full pipeline recommendations
        telegram_lightweight.j2 — lightweight health check
        telegram_error.j2 — error alerts
    """

    def __init__(self) -> None:
        self._bot: Bot | None = None
        self._jinja = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))

    def _get_bot(self) -> Bot | None:
        """Lazy-init the Telegram Bot. Returns None if token is missing."""
        if self._bot is None:
            token = settings.TELEGRAM_BOT_TOKEN
            if not token:
                logger.warning("TELEGRAM_BOT_TOKEN not configured — skipping push")
                return None
            self._bot = Bot(token=token)
        return self._bot

    async def send(self, state: PipelineState) -> None:
        """Dispatch to the appropriate send method based on pipeline_mode."""
        if state.pipeline_mode == "lightweight":
            await self._send_lightweight(state)
        else:
            await self._send_full(state)

    async def _send_full(self, state: PipelineState) -> None:
        """Send full pipeline results: recommendations, blocked, errors."""
        # Recommendations
        for rec in state.recommendations:
            msg = self._format_recommendation(rec)
            await self._send_message(msg)

        # Blocked recommendations
        for blocked in state.blocked_recommendations:
            msg = self._format_blocked(blocked)
            await self._send_message(msg)

        # Error alerts
        if state.error_flags:
            msg = self._format_errors(state.error_flags)
            await self._send_message(msg)

    async def _send_lightweight(self, state: PipelineState) -> None:
        """Send lightweight health check results."""
        template = self._jinja.get_template("telegram_lightweight.j2")
        msg = template.render(
            health_scores=state.health_scores,
            alerts=state.passive_health_alerts,
        )
        await self._send_message(msg)

    def _format_recommendation(self, rec: Any) -> str:
        """Format a single recommendation using the recommendation template."""
        template = self._jinja.get_template("telegram_recommendation.j2")
        return template.render(rec=rec)

    def _format_blocked(self, blocked: Any) -> str:
        """Format a blocked recommendation with warning prefix."""
        rec = blocked.recommendation
        return (
            f"⚠️ 被拦截推荐\n"
            f"{rec.ticker} — {rec.action.upper()} {rec.strategy}\n"
            f"拦截原因: {blocked.block_reason}\n"
            f"评分: {rec.score}/100"
        )

    def _format_errors(self, error_flags: list[dict[str, Any]]) -> str:
        """Format error alerts using the error template."""
        template = self._jinja.get_template("telegram_error.j2")
        return template.render(error_flags=error_flags)

    async def _send_message(self, text: str) -> None:
        """Send a message to Telegram, splitting if > 4000 chars."""
        bot = self._get_bot()
        if bot is None:
            return

        chat_id = settings.TELEGRAM_CHAT_ID
        if not chat_id:
            logger.warning("TELEGRAM_CHAT_ID not configured — skipping push")
            return

        prefix = "🧪 [Beta] "
        full_text = prefix + text

        try:
            if len(full_text) <= 4000:
                await bot.send_message(chat_id=chat_id, text=full_text)
            else:
                chunks = self._split_text(full_text, 4000)
                for i, chunk in enumerate(chunks, 1):
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"{chunk}\n({i}/{len(chunks)})",
                    )
        except TelegramError as exc:
            logger.error(f"Telegram send failed: {exc}")

    @staticmethod
    def _split_text(text: str, max_len: int) -> list[str]:
        """Split text into chunks ≤ max_len, preferring newline boundaries."""
        chunks: list[str] = []
        while len(text) > max_len:
            split_at = text.rfind("\n", 0, max_len)
            if split_at == -1:
                split_at = max_len
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        if text:
            chunks.append(text)
        return chunks
