"""E2E: Thesis lifecycle — create → validate → close → Memory → Weight."""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.skip(
    reason="Requires full SQLite database with thesis_cards, long_term_memory, and factor_weights tables. "
    "Run manually after setting up test data."
)
@pytest.mark.asyncio
async def test_full_thesis_lifecycle() -> None:
    """Full lifecycle: recommendation → thesis → validate → close → memory → weight."""
    pass