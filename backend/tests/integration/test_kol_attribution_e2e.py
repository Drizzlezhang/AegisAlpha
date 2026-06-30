"""E2E: KOL attribution — record call → wait 30d → attribute → update reliability."""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="Requires KOL calls with 30+ days of price history. "
    "Run manually after populating KOL data."
)
@pytest.mark.asyncio
async def test_kol_attribution_e2e() -> None:
    """E2E: record KOL call → attribution → reliability update."""
    pass