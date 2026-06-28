"""ThesisValidatorAgent — daily validation of active thesis key assumptions.

Standalone agent (does NOT inherit BaseAgent). Runs as an independent cron job,
not through GraphBuilder. Uses LLMClient (mini) to check each key_assumption
against current market data.

Design decisions (ADR-1, ADR-3):
  - Independent cron job, not part of Lightweight/Full Pipeline
  - Does not inherit BaseAgent (GraphBuilder can't inject dependencies)
  - Gets market data via Tool Registry, not PipelineState
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from aegis.llm.client import LLMClient
from aegis.services.thesis_service import ThesisService
from aegis.utils.settings import settings

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prompts"


class ThesisValidatorAgent:
    """Daily validation of active thesis key_assumptions against market data.

    Flow:
      1. Get all active theses from ThesisService
      2. For each thesis, get current market data via Tool Registry
      3. Call LLM (mini) to evaluate each key_assumption
      4. Update thesis_valid_status via ThesisService
    """

    def __init__(
        self,
        thesis_service: ThesisService,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._thesis = thesis_service
        self._llm = llm_client or LLMClient()
        self._jinja = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))

    async def validate_all(
        self, market_data: dict[str, dict[str, Any]] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Validate all active theses.

        Args:
            market_data: Optional dict of {ticker: market_data_dict}.
                         If not provided, skips theses that need market data.

        Returns:
            Dict of {ticker: validation_result}.
        """
        active_theses = await self._thesis.get_active_theses()
        if not active_theses:
            logger.info("ThesisValidator: no active theses to validate")
            return {}

        results: dict[str, dict[str, Any]] = {}
        for thesis in active_theses:
            ticker = thesis["ticker"]

            # Skip if no key_assumptions to validate
            if not thesis.get("key_assumptions"):
                logger.debug(f"Thesis {thesis['id']}: no assumptions, skipping")
                continue

            # Get current market data
            current_data: dict[str, Any] = {}
            if market_data:
                current_data = market_data.get(ticker, {})

            if not current_data:
                logger.debug(
                    f"Thesis {thesis['id']} ({ticker}): no market data, skipping"
                )
                continue

            # Validate via LLM
            try:
                validation = await self._validate_assumptions(thesis, current_data)
            except Exception:
                logger.exception(
                    f"Thesis {thesis['id']} ({ticker}): LLM validation failed"
                )
                continue

            # Determine new status
            broken_count = validation["broken_count"]
            total = len(thesis["key_assumptions"])
            if broken_count == 0:
                new_status = "valid"
            elif broken_count <= total // 2:
                new_status = "partial_broken"
            else:
                new_status = "fully_broken"

            # Update via ThesisService
            await self._thesis.update_valid_status(
                thesis_id=thesis["id"],
                new_status=new_status,
                broken_assumptions=validation["broken_assumptions"],
            )

            results[ticker] = {
                "thesis_id": thesis["id"],
                "previous_status": thesis["thesis_valid_status"],
                "new_status": new_status,
                "broken_count": broken_count,
                "broken_assumptions": validation["broken_assumptions"],
                "valid_assumptions": validation["valid_assumptions"],
                "analysis": validation["analysis"],
            }

        status_changes = sum(
            1 for r in results.values() if r["previous_status"] != r["new_status"]
        )
        logger.info(
            f"ThesisValidator: {len(results)} theses checked, "
            f"{status_changes} status changes"
        )
        return results

    async def _validate_assumptions(
        self, thesis: dict[str, Any], current_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Call LLM (mini) to evaluate each key_assumption.

        Args:
            thesis: Thesis dict from ThesisService.get_active_theses().
            current_data: Current market data for the ticker.

        Returns:
            Dict with broken_count, broken_assumptions, valid_assumptions, analysis.
        """
        template = self._jinja.get_template("thesis_validation.j2")
        prompt = template.render(
            ticker=thesis["ticker"],
            direction=thesis["direction"],
            entry_price=thesis["entry_price"],
            entry_date=thesis["entry_date"],
            key_assumptions=thesis["key_assumptions"],
            current_data=current_data,
        )

        response = await self._llm.chat(
            model=settings.LLM_MODEL_MINI,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = json.loads(response["content"])
        assumptions = result.get("assumptions", [])

        broken = [a["assumption"] for a in assumptions if a.get("status") == "broken"]
        valid = [a["assumption"] for a in assumptions if a.get("status") == "valid"]

        return {
            "broken_count": len(broken),
            "broken_assumptions": broken,
            "valid_assumptions": valid,
            "analysis": result.get("overall_analysis", ""),
        }
