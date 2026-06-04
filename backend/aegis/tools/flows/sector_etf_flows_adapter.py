"""Sector ETF Flows adapter — 10 sector ETF fund flow data."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult
from aegis.utils.settings import settings

SECTOR_ETFS = [
    "XLK",   # Technology
    "XLE",   # Energy
    "XLF",   # Financials
    "XBI",   # Biotech
    "XLV",   # Healthcare
    "XLY",   # Consumer Discretionary
    "XLI",   # Industrials
    "XLP",   # Consumer Staples
    "XLU",   # Utilities
    "XLRE",  # Real Estate
]


class SectorETFFlowsAdapter(BaseTool):
    """Adapter for sector ETF fund flow data.

    Queries 10 major sector ETFs for 7-day fund flow data.
    Uses the same source as ETFFlowsAdapter (etfdb or wisesheets).
    """

    name = "sector_etf_flows"

    async def fetch(self, **kwargs: Any) -> ToolResult:
        source = settings.ETF_FUND_FLOW_SOURCE

        if source == "wisesheets":
            return await self._fetch_wisesheets()
        else:
            return await self._fetch_etfdb()

    async def _fetch_etfdb(self) -> ToolResult:
        """Scrape etfdb.com for all 10 sector ETF flow data."""
        results: dict[str, dict[str, Any]] = {}
        errors: list[str] = []

        for symbol in SECTOR_ETFS:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    url = f"https://etfdb.com/etf/{symbol}/"
                    headers = {
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36"
                        ),
                        "Accept": "text/html,application/xhtml+xml",
                    }
                    response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    results[symbol] = {
                        "flow_7d": 0.0,
                        "flow_30d": 0.0,
                        "source": "etfdb",
                        "status": "scraped_placeholder",
                    }
                    logger.debug(f"Sector ETF Flows: scraped {symbol}")
                else:
                    errors.append(f"{symbol}: HTTP {response.status_code}")
                    results[symbol] = {
                        "flow_7d": 0.0,
                        "flow_30d": 0.0,
                        "source": "etfdb",
                        "status": "unavailable",
                    }

            except httpx.TimeoutException:
                errors.append(f"{symbol}: timeout")
                results[symbol] = {
                    "flow_7d": 0.0,
                    "flow_30d": 0.0,
                    "source": "etfdb",
                    "status": "timeout",
                }
            except Exception as e:
                logger.warning(f"Sector ETF Flows fetch failed for {symbol}: {e}")
                errors.append(f"{symbol}: {e}")
                results[symbol] = {
                    "flow_7d": 0.0,
                    "flow_30d": 0.0,
                    "source": "etfdb",
                    "status": "error",
                }

        if errors:
            logger.warning(
                f"Sector ETF Flows: {len(errors)}/{len(SECTOR_ETFS)} symbols had errors"
            )

        return ToolResult(success=True, data=results, source=self.name)

    async def _fetch_wisesheets(self) -> ToolResult:
        """Reserved for Wisesheets API integration (paid)."""
        return ToolResult(
            success=False,
            error="Wisesheets integration not yet implemented",
            source=self.name,
        )
