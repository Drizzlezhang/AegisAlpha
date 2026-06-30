"""
E2E: ReportGenerator — weekly and monthly report generation.

Verifies: data collection → structured report → markdown → storage.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.services.report_generator import ReportGenerator


@pytest.fixture
def mock_memory() -> AsyncMock:
    memory = AsyncMock()
    memory.read = AsyncMock(return_value=[])
    memory.summarize = AsyncMock(
        return_value={"count": 0, "date_range": ("2026-01-01", "2026-01-07"), "data_types": {}}
    )
    return memory


@pytest.fixture
def mock_weight_store() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_thesis_store() -> AsyncMock:
    store = AsyncMock()
    store.get_active = AsyncMock(return_value=[])
    store.list_all = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_kol_store() -> AsyncMock:
    store = AsyncMock()
    store.get_attribution_stats = AsyncMock(
        return_value={"total": 0, "validated": 0, "invalidated": 0, "pending": 0}
    )
    store.list_sources = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock()
    llm.chat = AsyncMock(return_value="# Weekly Report\n\nNo data.")
    return llm


@pytest.fixture
def generator(mock_memory, mock_weight_store, mock_thesis_store, mock_kol_store, mock_llm):
    return ReportGenerator(
        memory=mock_memory,
        weight_store=mock_weight_store,
        thesis_store=mock_thesis_store,
        kol_store=mock_kol_store,
        llm_client=mock_llm,
    )


@pytest.mark.asyncio
async def test_generate_weekly_returns_report_structure(generator):
    """Weekly report should contain type, date, period, sections, markdown."""
    report = await generator.generate_weekly()

    assert report["type"] == "weekly"
    assert "date" in report
    assert "period" in report
    assert "sections" in report
    assert "markdown" in report
    assert report["period"]["end"] == date.today().isoformat()


@pytest.mark.asyncio
async def test_generate_monthly_returns_report_structure(generator):
    """Monthly report should contain type, date, period, sections, markdown."""
    report = await generator.generate_monthly()

    assert report["type"] == "monthly"
    assert "date" in report
    assert "period" in report
    assert "sections" in report
    assert "markdown" in report
    assert "pnl_summary" in report["sections"]


@pytest.mark.asyncio
async def test_generate_weekly_fallback_on_llm_failure(generator, mock_llm):
    """When LLM fails, fallback markdown should be generated."""
    mock_llm.chat = AsyncMock(side_effect=Exception("LLM unavailable"))

    report = await generator.generate_weekly()

    assert "Aegis Weekly Report" in report["markdown"]
    assert "Period" in report["markdown"]


@pytest.mark.asyncio
async def test_list_reports_returns_empty_when_no_reports(generator, mock_memory):
    """list_reports should return empty list when no reports stored."""
    mock_memory.read = AsyncMock(return_value=[])

    reports = await generator.list_reports()

    assert reports == []
    assert isinstance(reports, list)


@pytest.mark.asyncio
async def test_list_reports_filters_by_type(generator, mock_memory):
    """list_reports should filter by report_type."""
    mock_memory.read = AsyncMock(
        return_value=[
            {
                "content": {
                    "type": "weekly",
                    "date": "2026-06-28",
                    "period": {"start": "2026-06-22", "end": "2026-06-28"},
                }
            },
            {
                "content": {
                    "type": "monthly",
                    "date": "2026-06-01",
                    "period": {"start": "2026-05-01", "end": "2026-05-31"},
                }
            },
        ]
    )

    weekly = await generator.list_reports(report_type="weekly")
    assert len(weekly) == 1
    assert weekly[0]["type"] == "weekly"

    monthly = await generator.list_reports(report_type="monthly")
    assert len(monthly) == 1
    assert monthly[0]["type"] == "monthly"


@pytest.mark.asyncio
async def test_get_report_returns_none_when_not_found(generator, mock_memory):
    """get_report should return None when report not found."""
    mock_memory.read = AsyncMock(return_value=[])

    result = await generator.get_report("weekly", "2026-01-01")

    assert result is None


@pytest.mark.asyncio
async def test_get_report_returns_found_report(generator, mock_memory):
    """get_report should return the report content when found."""
    expected = {
        "type": "weekly",
        "date": "2026-06-28",
        "period": {"start": "2026-06-22", "end": "2026-06-28"},
        "sections": {},
        "markdown": "# Test",
    }
    mock_memory.read = AsyncMock(return_value=[{"content": expected}])

    result = await generator.get_report("weekly", "2026-06-28")

    assert result == expected