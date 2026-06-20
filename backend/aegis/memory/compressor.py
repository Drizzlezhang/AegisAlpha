"""MemoryCompressor — batch compression of old long-term memory records via LLM."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import groupby
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from aegis.llm.client import LLMClient
from aegis.memory.long_term_store import LongTermStore
from aegis.memory.vector_store import VectorStore
from aegis.utils.settings import settings


class MemoryCompressor:
    """Compresses old long-term memory records into LLM-generated summaries.

    Iterates compression_windows from memory.yaml, groups uncompressed records
    by ticker, generates summaries via LLM_MODEL_MINI, writes compressed records
    and vectorizes them.
    """

    def __init__(
        self,
        long_term_store: LongTermStore,
        vector_store: VectorStore,
        llm_client: LLMClient,
        config: dict[str, Any],
    ) -> None:
        self._long_term = long_term_store
        self._vector = vector_store
        self._llm = llm_client
        self._config = config

        # Jinja2 environment for prompt templates
        template_dir = str(Path(__file__).resolve().parent.parent.parent / "config" / "prompts")
        self._jinja_env = Environment(loader=FileSystemLoader(template_dir))

    async def run_compression(self) -> dict[str, int]:
        """Run compression for all data_types defined in compression_windows.

        Returns:
            Dict mapping data_type to number of records compressed.
        """
        compression_windows = self._config.get("long_term", {}).get("compression_windows", {})
        if not compression_windows:
            logger.info("MemoryCompressor: no compression_windows configured, skipping")
            return {}

        stats: dict[str, int] = {}
        for data_type, window_cfg in compression_windows.items():
            full_days = window_cfg.get("full_days", 60)
            cutoff = datetime.now(UTC) - timedelta(days=full_days)
            records = self._long_term.get_uncompressed_before(data_type, cutoff)

            if not records:
                stats[data_type] = 0
                continue

            # Group by ticker
            records.sort(key=lambda r: r.get("ticker") or "")
            for ticker, group_iter in groupby(records, key=lambda r: r.get("ticker") or ""):
                group = list(group_iter)
                try:
                    summary = await self._generate_summary(data_type, ticker, group)
                except Exception:
                    logger.exception(
                        f"MemoryCompressor: LLM summary failed for {data_type}/{ticker}"
                    )
                    continue

                # Write summary as a new compressed long-term record
                date_range = (
                    group[0]["original_date"],
                    group[-1]["original_date"],
                )
                summary_id = self._long_term.insert(
                    {
                        "ticker": ticker or None,
                        "data_type": data_type,
                        "content": {
                            "summary": summary,
                            "compressed_from": len(group),
                            "date_range": list(date_range),
                        },
                        "summary": summary,
                        "original_date": datetime.now(UTC),
                        "is_compressed": True,
                    }
                )

                # Vectorize the summary
                embedding_id = None
                try:
                    doc_id = f"{data_type}_{ticker}_{summary_id}"
                    success = await self._vector.add(
                        collection=data_type,
                        doc_id=doc_id,
                        text=summary,
                        metadata={
                            "ticker": ticker,
                            "data_type": data_type,
                            "record_count": len(group),
                            "date_from": date_range[0],
                            "date_to": date_range[1],
                        },
                    )
                    if success:
                        embedding_id = doc_id
                except Exception:
                    logger.warning(
                        f"MemoryCompressor: vectorization failed for {data_type}/{ticker}"
                    )

                # Mark originals as compressed
                original_ids = [r["id"] for r in group]
                self._long_term.mark_compressed(original_ids, summary, embedding_id)

            stats[data_type] = len(records)
            logger.info(f"MemoryCompressor: {data_type} — {len(records)} records compressed")

        return stats

    async def _generate_summary(
        self, data_type: str, ticker: str, records: list[dict[str, Any]]
    ) -> str:
        """Generate an LLM summary for a group of records.

        Args:
            data_type: The data_type being compressed.
            ticker: The ticker symbol.
            records: List of record dicts to summarize.

        Returns:
            LLM-generated summary text.
        """
        template = self._load_template(data_type)
        date_range = (
            records[0]["original_date"],
            records[-1]["original_date"],
        )
        prompt = template.render(
            ticker=ticker,
            records=records,
            record_count=len(records),
            date_range=date_range,
            data_type=data_type,
        )

        response = await self._llm.chat(
            model=settings.LLM_MODEL_MINI,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return str(response.get("content", ""))

    def _load_template(self, data_type: str) -> Any:
        """Load Jinja2 template, falling back to default if specific one missing."""
        specific_name = f"memory_compression_{data_type}.j2"
        try:
            return self._jinja_env.get_template(specific_name)
        except Exception:
            logger.debug(f"Template {specific_name} not found, using memory_compression_default.j2")
            return self._jinja_env.get_template("memory_compression_default.j2")
