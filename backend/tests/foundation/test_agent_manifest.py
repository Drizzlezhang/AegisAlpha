"""Test AgentManifest contract — field completeness and constraints."""
import pytest
from pydantic import ValidationError

from aegis.registry.agent_registry import AgentManifest


class TestAgentManifest:
    """Verify AgentManifest v1.2 schema."""

    def test_all_fields_exist(self) -> None:
        """AgentManifest should have all required fields."""
        m = AgentManifest(name="test")
        assert m.name == "test"
        assert m.version == "0.1.0"
        assert m.requires == []
        assert m.provides == []
        assert m.tags == []
        assert m.llm_dependency is True
        assert m.parallel_group is None
        assert m.pipeline_mode == "full"
        assert m.enabled is True

    def test_pipeline_mode_literal_valid(self) -> None:
        """pipeline_mode should accept 'full', 'lightweight', 'both'."""
        for mode in ("full", "lightweight", "both"):
            m = AgentManifest(name="test", pipeline_mode=mode)
            assert m.pipeline_mode == mode

    def test_pipeline_mode_literal_invalid(self) -> None:
        """pipeline_mode should reject invalid values."""
        with pytest.raises(ValidationError):
            AgentManifest(name="test", pipeline_mode="invalid")

    def test_enabled_default(self) -> None:
        """enabled should default to True."""
        m = AgentManifest(name="test")
        assert m.enabled is True

    def test_llm_dependency_default(self) -> None:
        """llm_dependency should default to True."""
        m = AgentManifest(name="test")
        assert m.llm_dependency is True

    def test_parallel_group_optional(self) -> None:
        """parallel_group should accept None or a string."""
        m1 = AgentManifest(name="test")
        assert m1.parallel_group is None

        m2 = AgentManifest(name="test", parallel_group="signal_group")
        assert m2.parallel_group == "signal_group"

    def test_tags_list(self) -> None:
        """tags should accept a list of strings."""
        m = AgentManifest(name="test", tags=["signal", "options", "macro"])
        assert m.tags == ["signal", "options", "macro"]

    def test_requires_provides_lists(self) -> None:
        """requires and provides should accept lists of strings."""
        m = AgentManifest(
            name="test",
            requires=["tickers", "market_data"],
            provides=["analyst_outputs", "extensions.test"],
        )
        assert m.requires == ["tickers", "market_data"]
        assert m.provides == ["analyst_outputs", "extensions.test"]
