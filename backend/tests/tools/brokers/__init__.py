"""Tests for BrokerPosition model and BrokerAdapter interface."""

import pytest

from aegis.tools.brokers.base import BrokerAdapter, BrokerPosition


class TestBrokerPosition:
    """AC-1: BrokerPosition model field validation."""

    def test_minimal_position(self) -> None:
        """Minimal required fields should create valid model."""
        pos = BrokerPosition(account="futu", ticker="QQQ", pos_type="stock", quantity=100, avg_cost=350.0)
        assert pos.account == "futu"
        assert pos.ticker == "QQQ"
        assert pos.pos_type == "stock"
        assert pos.quantity == 100
        assert pos.avg_cost == 350.0

    def test_all_18_fields_exist(self) -> None:
        """All 18 fields should be present in model_fields."""
        fields = BrokerPosition.model_fields
        expected = {
            "account", "ticker", "pos_type", "quantity", "avg_cost",
            "current_price", "strike", "expiry", "option_type",
            "delta", "gamma", "theta", "vega", "iv",
            "delta_dollars", "unrealized_pnl", "entry_mode", "grade",
        }
        assert set(fields.keys()) == expected

    def test_optional_fields_default_to_none(self) -> None:
        """Optional fields should default to None."""
        pos = BrokerPosition(account="futu", ticker="QQQ", pos_type="stock", quantity=100, avg_cost=350.0)
        assert pos.current_price is None
        assert pos.strike is None
        assert pos.expiry is None
        assert pos.option_type is None
        assert pos.delta is None
        assert pos.gamma is None
        assert pos.theta is None
        assert pos.vega is None
        assert pos.iv is None
        assert pos.delta_dollars is None
        assert pos.unrealized_pnl is None
        assert pos.entry_mode is None
        assert pos.grade is None

    def test_full_option_position(self) -> None:
        """Full option position with all fields populated."""
        pos = BrokerPosition(
            account="futu",
            ticker="QQQ",
            pos_type="option",
            quantity=10,
            avg_cost=5.0,
            current_price=6.5,
            strike=400.0,
            expiry="2025-12-19",
            option_type="call",
            delta=0.65,
            gamma=0.02,
            theta=-0.05,
            vega=0.15,
            iv=0.22,
            delta_dollars=26000.0,
            unrealized_pnl=1500.0,
            entry_mode="active_right",
            grade="active",
        )
        assert pos.pos_type == "option"
        assert pos.strike == 400.0
        assert pos.option_type == "call"
        assert pos.delta == 0.65
        assert pos.delta_dollars == 26000.0
        assert pos.entry_mode == "active_right"


class TestBrokerAdapter:
    """AC-1: BrokerAdapter interface contract."""

    def test_is_abstract(self) -> None:
        """BrokerAdapter should be abstract."""
        with pytest.raises(TypeError):
            BrokerAdapter()  # type: ignore[abstract]

    def test_has_four_abstract_methods(self) -> None:
        """BrokerAdapter should have 4 abstract methods."""
        assert hasattr(BrokerAdapter, "get_positions")
        assert hasattr(BrokerAdapter, "get_account_summary")
        assert hasattr(BrokerAdapter, "get_options_chain")
        assert hasattr(BrokerAdapter, "get_oi_data")
