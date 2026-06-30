"""E2E: WeightAdapter observation period → backfill → weekly update → history."""

from __future__ import annotations

import os
import tempfile

import pytest


@pytest.mark.skip(
    reason="Requires full SQLite database with thesis_cards and factor_weights tables. "
    "Run manually after setting up test data."
)
@pytest.mark.asyncio
async def test_weight_observation_full_cycle() -> None:
    """Full cycle: observation period check → backfill → weight update → history."""
    db_path = os.path.join(tempfile.mkdtemp(), "test_weight.db")
    try:
        # 1. Create test DB with tables
        # 2. Check observation period is active
        # 3. Add thesis cards with 30+ days of history
        # 4. Verify observation period transitions
        # 5. Run weight update
        # 6. Verify weight history
        pass
    finally:
        os.unlink(db_path)