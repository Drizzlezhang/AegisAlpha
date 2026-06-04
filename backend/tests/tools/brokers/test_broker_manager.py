"""Tests for BrokerManager — multi-broker aggregation."""

import asyncio

import pytest

from aegis.tools.brokers.base import BrokerAdapter, BrokerPosition
from aegis.tools.brokers.manager import BrokerManager


class MockBroker(BrokerAdapter):
    """Mock broker for testing."""

    def __init__(self, name: str, positions: list[BrokerPosition] | None = None, should_fail: bool = False) -> None:
        self._name = name
        self._positions = positions or []
        self._should_fail = should_fail

    async def get_positions(self) -> list[BrokerPosition]:
        if self._should_fail:
            raise RuntimeError(f"{self._name} connection failed")
        return self._positions

    async def get_account_summary(self) -> dict:
        if self._should_fail:
            raise RuntimeError(f"{self._name} connection failed")
        return {"nav": 100000, "cash": 20000, "margin": 0, "market_value": 80000}

    async def get_options_chain(self, ticker: str, expiry: str | None = None) -> list[dict]:
        return []

    async def get_oi_data(self, ticker: str) -> dict:
        return {"ticker": ticker, "total_open_interest": 0}


class TestBrokerManager:
    """AC-5: BrokerManager aggregation and fallback."""

    def test_aggregate_delta_dollars(self) -> None:
        positions = [
            BrokerPosition(account="a", ticker="QQQ", pos_type="stock", quantity=100, avg_cost=350, delta_dollars=35000),
            BrokerPosition(account="b", ticker="SPY", pos_type="stock", quantity=50, avg_cost=450, delta_dollars=22500),
        ]
        assert BrokerManager.aggregate_delta_dollars(positions) == 57500.0

    def test_aggregate_delta_dollars_none_values(self) -> None:
        positions = [
            BrokerPosition(account="a", ticker="QQQ", pos_type="stock", quantity=100, avg_cost=350),
            BrokerPosition(account="b", ticker="SPY", pos_type="stock", quantity=50, avg_cost=450, delta_dollars=22500),
        ]
        assert BrokerManager.aggregate_delta_dollars(positions) == 22500.0

    def test_empty_adapters(self) -> None:
        manager = BrokerManager([])
        result = asyncio.run(manager.get_all_positions())
        assert result == []

    def test_single_broker(self) -> None:
        pos = BrokerPosition(account="futu", ticker="QQQ", pos_type="stock", quantity=100, avg_cost=350)
        broker = MockBroker("futu", [pos])
        manager = BrokerManager([broker])
        result = asyncio.run(manager.get_all_positions())
        assert len(result) == 1
        assert result[0].ticker == "QQQ"

    def test_multi_broker_merge(self) -> None:
        pos1 = BrokerPosition(account="futu", ticker="QQQ", pos_type="stock", quantity=100, avg_cost=350)
        pos2 = BrokerPosition(account="longbridge", ticker="SPY", pos_type="stock", quantity=50, avg_cost=450)
        manager = BrokerManager([
            MockBroker("futu", [pos1]),
            MockBroker("longbridge", [pos2]),
        ])
        result = asyncio.run(manager.get_all_positions())
        assert len(result) == 2

    def test_partial_failure(self) -> None:
        """AC-5: single broker failure should not block others."""
        pos = BrokerPosition(account="futu", ticker="QQQ", pos_type="stock", quantity=100, avg_cost=350)
        manager = BrokerManager([
            MockBroker("futu", [pos]),
            MockBroker("longbridge", should_fail=True),
        ])
        result = asyncio.run(manager.get_all_positions())
        assert len(result) == 1
        assert result[0].ticker == "QQQ"

    def test_all_failure(self) -> None:
        """All brokers fail should return empty list."""
        manager = BrokerManager([
            MockBroker("futu", should_fail=True),
            MockBroker("longbridge", should_fail=True),
        ])
        result = asyncio.run(manager.get_all_positions())
        assert result == []

    def test_merged_summary(self) -> None:
        manager = BrokerManager([
            MockBroker("futu"),
            MockBroker("longbridge"),
        ])
        result = asyncio.run(manager.get_merged_summary())
        assert result["total_nav"] == 200000
        assert result["total_cash"] == 40000
