"""Broker adapter base classes and data models.

Defines the unified BrokerAdapter interface and BrokerPosition Pydantic model
that all broker-specific adapters must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class BrokerPosition(BaseModel):
    """Unified position model across all brokers."""

    account: str
    ticker: str
    pos_type: str  # "stock" / "option"
    quantity: int
    avg_cost: float
    current_price: float | None = None
    strike: float | None = None
    expiry: str | None = None  # YYYY-MM-DD
    option_type: str | None = None  # "call" / "put"
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    iv: float | None = None
    delta_dollars: float | None = None
    unrealized_pnl: float | None = None
    entry_mode: str | None = None  # passive / active_left / active_right / cc / sell_put
    grade: str | None = None  # passive / active


class BrokerAdapter(ABC):
    """Unified broker interface.

    All broker adapters must implement these four async methods.
    SDK imports should be lazy (inside __init__ or method body) to avoid
    import errors when a broker SDK is not installed.
    """

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Fetch all positions from the broker."""

    @abstractmethod
    async def get_account_summary(self) -> dict[str, Any]:
        """Fetch account summary: NAV, cash, margin."""

    @abstractmethod
    async def get_options_chain(
        self, ticker: str, expiry: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetch options chain for a ticker (optional fallback for yFinance)."""

    @abstractmethod
    async def get_oi_data(self, ticker: str) -> dict[str, Any]:
        """Fetch Open Interest data for Smart Money Agent."""
