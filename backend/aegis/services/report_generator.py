"""ReportGenerator — weekly/monthly report generation.

Generates structured reports from Memory, Thesis, KOL, and Weight data,
then uses LLM to produce a Markdown summary. Reports are stored in
long-term memory for later retrieval by the frontend.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from aegis.llm.client import LLMClient
from aegis.memory.service import MemoryService
from aegis.memory.weight_store import WeightStore
from aegis.storage.kol_store import KOLStore
from aegis.storage.thesis_store import ThesisStore
from aegis.utils.settings import settings


class ReportGenerator:
    """Auto-generates weekly and monthly performance reports.

    Weekly (every Sunday):
        - Recommendations this week + success rate
        - Active Thesis status
        - Factor performance (which factors predicted correctly)
        - KOL attribution this week
        - Memory compression stats

    Monthly (1st of month):
        - Monthly P&L summary
        - Weight change trends
        - Thesis health (active/closed/broken)
        - KOL leaderboard
        - Strategy reflection
    """

    def __init__(
        self,
        memory: MemoryService,
        weight_store: WeightStore,
        thesis_store: ThesisStore,
        kol_store: KOLStore,
        llm_client: LLMClient,
    ) -> None:
        self._memory = memory
        self._weight_store = weight_store
        self._thesis_store = thesis_store
        self._kol_store = kol_store
        self._llm = llm_client

    # ------------------------------------------------------------------
    # Weekly
    # ------------------------------------------------------------------

    async def generate_weekly(self) -> dict[str, Any]:
        """Generate a weekly report for the past 7 days.

        Returns:
            Dict with type, date, period, sections, and markdown.
        """
        today = date.today()
        week_start = today - timedelta(days=7)

        # Collect data
        recommendations = await self._memory.read(
            "long",
            {"data_type": "recommendation"},
            limit=100,
        )
        # Filter to this week
        recs_this_week = [
            r
            for r in recommendations
            if r.get("original_date", "") >= week_start.isoformat()
        ][:10]

        active_theses = await self._thesis_store.get_active()
        closed_cards = await self._thesis_store.list_all(
            {"status": "closed"}, limit=100
        )
        closed_this_week = [
            t
            for t in closed_cards
            if t.close_date and t.close_date.date() >= week_start
        ]

        kol_stats = await self._kol_store.get_attribution_stats()

        report = {
            "type": "weekly",
            "date": today.isoformat(),
            "period": {"start": week_start.isoformat(), "end": today.isoformat()},
            "sections": {
                "recommendations": {
                    "total": len(recs_this_week),
                    "items": [
                        {
                            "ticker": r.get("ticker", ""),
                            "direction": r.get("direction", ""),
                            "entry_price": r.get("entry_price"),
                        }
                        for r in recs_this_week
                    ],
                },
                "thesis_status": {
                    "active_count": len(active_theses),
                    "closed_this_week": len(closed_this_week),
                    "pnl_this_week": round(
                        sum(t.actual_pnl_pct or 0 for t in closed_this_week), 4
                    ),
                },
                "kol_attribution": kol_stats,
                "memory": await self._memory.summarize(
                    ticker=None,
                    date_range=(week_start.isoformat(), today.isoformat()),
                    data_type="",
                ),
            },
        }

        # Generate Markdown summary
        try:
            report["markdown"] = await self._generate_markdown(report, "weekly")
        except Exception:
            logger.exception("ReportGenerator: LLM markdown generation failed")
            report["markdown"] = self._fallback_markdown(report, "weekly")

        # Store in long-term memory
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import Session as _Session

            engine = create_engine(settings.DATABASE_URL)
            with _Session(engine) as session:
                from aegis.memory.long_term_store import LongTermStore

                long_term = LongTermStore(lambda: session)
                long_term.insert({
                    "ticker": "",
                    "data_type": "report",
                    "content": {
                        "type": "weekly",
                        "date": today.isoformat(),
                        "period": report["period"],
                        "sections": report["sections"],
                        "markdown": report["markdown"],
                    },
                    "original_date": datetime.now(UTC),
                })
            engine.dispose()
        except Exception:
            logger.exception("ReportGenerator: failed to store weekly report")

        logger.info(f"ReportGenerator: weekly report generated ({today.isoformat()})")
        return report

    # ------------------------------------------------------------------
    # Monthly
    # ------------------------------------------------------------------

    async def generate_monthly(self) -> dict[str, Any]:
        """Generate a monthly report for the previous calendar month.

        Returns:
            Dict with type, date, period, sections, and markdown.
        """
        today = date.today()
        month_start = today.replace(day=1)
        prev_month_end = month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)

        # Collect data
        closed_cards = await self._thesis_store.list_all(
            {"status": "closed"}, limit=200
        )
        last_month_closed = [
            t
            for t in closed_cards
            if t.close_date
            and prev_month_start <= t.close_date.date() <= prev_month_end
        ]

        total_pnl = sum(t.actual_pnl_pct or 0 for t in last_month_closed)
        win_count = sum(1 for t in last_month_closed if (t.actual_pnl_pct or 0) > 0)
        trade_count = max(len(last_month_closed), 1)

        active_theses = await self._thesis_store.get_active()
        sources = await self._kol_store.list_sources(enabled_only=False)

        report = {
            "type": "monthly",
            "date": today.isoformat(),
            "period": {
                "start": prev_month_start.isoformat(),
                "end": prev_month_end.isoformat(),
            },
            "sections": {
                "pnl_summary": {
                    "total_pnl_pct": round(total_pnl, 4),
                    "trades_closed": len(last_month_closed),
                    "win_rate": round(win_count / trade_count, 4),
                    "avg_pnl": round(total_pnl / trade_count, 4),
                },
                "thesis_health": {
                    "active": len(active_theses),
                    "closed_month": len(last_month_closed),
                },
                "kol_leaderboard": [
                    {
                        "name": s.name,
                        "reliability_score": s.reliability_score,
                        "total_calls": s.total_calls,
                        "success_rate": (
                            s.successful_calls / max(s.total_calls, 1)
                        ),
                    }
                    for s in sorted(
                        sources,
                        key=lambda x: x.reliability_score,
                        reverse=True,
                    )[:10]
                ],
            },
        }

        # Generate Markdown summary
        try:
            report["markdown"] = await self._generate_markdown(report, "monthly")
        except Exception:
            logger.exception("ReportGenerator: LLM markdown generation failed")
            report["markdown"] = self._fallback_markdown(report, "monthly")

        # Store in long-term memory
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import Session as _Session

            engine = create_engine(settings.DATABASE_URL)
            with _Session(engine) as session:
                from aegis.memory.long_term_store import LongTermStore

                long_term = LongTermStore(lambda: session)
                long_term.insert({
                    "ticker": "",
                    "data_type": "report",
                    "content": {
                        "type": "monthly",
                        "date": today.isoformat(),
                        "period": report["period"],
                        "sections": report["sections"],
                        "markdown": report["markdown"],
                    },
                    "original_date": datetime.now(UTC),
                })
            engine.dispose()
        except Exception:
            logger.exception("ReportGenerator: failed to store monthly report")

        logger.info(f"ReportGenerator: monthly report generated ({today.isoformat()})")
        return report

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def get_report(
        self, report_type: str, report_date: str
    ) -> dict[str, Any] | None:
        """Get a specific report by type and date."""
        records = await self._memory.read(
            "long",
            {"data_type": "report"},
            limit=50,
        )

        for r in records:
            content = r.get("content", {})
            if content.get("type") == report_type and content.get("date") == report_date:
                return dict(content)
        return None

    async def list_reports(
        self, report_type: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """List available reports, optionally filtered by type."""
        records = await self._memory.read(
            "long",
            {"data_type": "report"},
            limit=max(limit * 2, 50),  # fetch extra to filter
        )

        results: list[dict[str, Any]] = []
        for r in records:
            content = r.get("content", {})
            if report_type and content.get("type") != report_type:
                continue
            results.append({
                "type": content.get("type", ""),
                "date": content.get("date", ""),
                "period": content.get("period", {}),
            })
            if len(results) >= limit:
                break

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _generate_markdown(
        self, report: dict[str, Any], report_type: str
    ) -> str:
        """Use LLM to convert structured report into Markdown."""
        config_dir = (
            Path(__file__).resolve().parent.parent.parent / "config" / "prompts"
        )
        env = Environment(loader=FileSystemLoader(str(config_dir)))
        template = env.get_template(f"report_{report_type}.j2")
        prompt = template.render(report=report)

        result = await self._llm.chat(
            model=settings.LLM_MODEL_MINI,
            messages=[{"role": "user", "content": prompt}],
        )
        return str(result)

    @staticmethod
    def _fallback_markdown(report: dict[str, Any], report_type: str) -> str:
        """Generate a plain text summary when LLM is unavailable."""
        title = "Weekly" if report_type == "weekly" else "Monthly"
        lines = [f"# Aegis {title} Report", ""]
        period = report.get("period", {})
        lines.append(
            f"Period: {period.get('start', 'N/A')} → {period.get('end', 'N/A')}"
        )
        lines.append("")

        sections = report.get("sections", {})
        for section_name, section_data in sections.items():
            lines.append(f"## {section_name.replace('_', ' ').title()}")
            for key, value in section_data.items():
                lines.append(f"- {key}: {value}")
            lines.append("")

        return "\n".join(lines)
