"""Report routes — GET /api/v1/reports, generate, retrieve."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from aegis.api.deps import get_report_generator
from aegis.services.report_generator import ReportGenerator

router = APIRouter(tags=["reports"])


@router.get("/reports")
async def list_reports(
    report_type: str | None = Query(
        None, pattern="^(weekly|monthly)$"
    ),
    limit: int = Query(10, ge=1, le=50),
    generator: ReportGenerator = Depends(get_report_generator),  # noqa: B008
) -> list[dict[str, Any]]:
    """List available reports, optionally filtered by type."""
    return await generator.list_reports(report_type, limit)


@router.get("/reports/{report_type}/{report_date}")
async def get_report(
    report_type: str,
    report_date: str,
    generator: ReportGenerator = Depends(get_report_generator),  # noqa: B008
) -> dict[str, Any]:
    """Get a specific report by type and date."""
    report = await generator.get_report(report_type, report_date)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.post("/reports/generate")
async def trigger_generation(
    report_type: str = Query(..., pattern="^(weekly|monthly)$"),
    generator: ReportGenerator = Depends(get_report_generator),  # noqa: B008
) -> dict[str, Any]:
    """Manually trigger report generation."""
    if report_type == "weekly":
        return await generator.generate_weekly()
    else:
        return await generator.generate_monthly()
