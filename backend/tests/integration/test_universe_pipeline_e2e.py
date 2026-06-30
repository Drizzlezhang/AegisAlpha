"""E2E: Universe scan → candidates → inject into Pipeline."""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="Requires Universe Triage agent and market data. "
    "Run manually after setting up Universe agent."
)
@pytest.mark.asyncio
async def test_universe_pipeline_e2e() -> None:
    """E2E: scan → candidates → pipeline injection."""
    pass