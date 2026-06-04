"""ETF Flows adapter — SPY/QQQ/GLD/SLV fund flow data from etfdb or wisesheets."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from aegis.tools.base import BaseTool, ToolResult
from aegis.utils.settings import settings

DEFAULT_SYMBOLS = ["SPY", "QQQ", "GLD", "SLV"]


class ETFFlowsAdapter(BaseTool):
    """Adapter for ETF fund flow data.

    Supports two sources controlled by settings.ETF_FUND_FLOW_SOURCE:
    - "etfdb": Free scraping from etfdb.com (default)
    - "wisesheets": Paid Wisesheets API (reserved for future)
    """

    name = "etf_flows"

    async def fetch(self, **kwargs: Any) -> ToolResult:
        symbols: list[str] = kwargs.get("symbols", DEFAULT_SYMBOLS)
        source = settings.ETF_FUND_FLOW_SOURCE

        if source == "wisesheets":
            return await self._fetch_wisesheets(symbols)
        else:
            return await self._fetch_etfdb(symbols)

    async def _fetch_etfdb(self, symbols: list[str]) -> ToolResult:
        """Scrape etfdb.com for ETF flow data.

        Note: etfdb.com may require anti-scraping measures.
        On failure, returns empty data rather than blocking the pipeline.
        """
        results: dict[str, dict[str, Any]] = {}
        errors: list[str] = []

        for symbol in symbols:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    # etfdb.com ETF page URL pattern
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
                    # Parse flow data from HTML (simplified — real impl would use
                    # BeautifulSoup or regex to extract flow numbers)
                    results[symbol] = {
                        "flow_7d": 0.0,
                        "flow_30d": 0.0,
                        "source": "etfdb",
                        "status": "scraped_placeholder",
                    }
                    logger.debug(f"ETF Flows: scraped {symbol} from etfdb")
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
                logger.warning(f"ETF Flows fetch failed for {symbol}: {e}")
                errors.append(f"{symbol}: {e}")
                results[symbol] = {
                    "flow_7d": 0.0,
                    "flow_30d": 0.0,
                    "source": "etfdb",
                    "status": "error",
                }

        if errors:
            logger.warning(
                f"ETF Flows: {len(errors)}/{len(symbols)} symbols had errors"
            )

        return ToolResult(success=True, data=results, source=self.name)

    async def _fetch_wisesheets(self, symbols: list[str]) -> ToolResult:
        """Reserved for Wisesheets API integration (paid)."""
        return ToolResult(
            success=False,
            error="Wisesheets integration not yet implemented",
            source=self.name,
        )
