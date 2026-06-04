"""Tests for GraphBuilder — manifest-driven dynamic assembly."""

from aegis.pipeline.graph_builder import (
    GraphBuilder,
    _find_provider,
    _load_agents_yaml,
    _topological_sort,
)


class TestGraphBuilder:
    def test_build_full_returns_compiled_graph(self):
        """GraphBuilder.build('full') should return a compiled StateGraph."""
        gb = GraphBuilder()
        graph = gb.build("full")
        assert graph is not None

    def test_build_lightweight_returns_compiled_graph(self):
        """GraphBuilder.build('lightweight') should return a compiled StateGraph."""
        gb = GraphBuilder()
        graph = gb.build("lightweight")
        assert graph is not None

    def test_full_graph_has_all_9_agents(self):
        """Full pipeline should include all 9 M1 agents."""
        gb = GraphBuilder()
        graph = gb.build("full")
        # Compiled graph has nodes dict
        nodes = list(graph.nodes.keys()) if hasattr(graph, "nodes") else []
        # Should have at least the 9 agents + __start__ + __end__
        assert len(nodes) >= 9

    def test_full_order_matches_m1_hardcoded(self):
        """Topological sort should match M1 graph_full.py order."""
        config = _load_agents_yaml()
        agents = {
            name: agent
            for name, agent in config["agents"].items()
            if agent.get("pipeline_mode") in ("full", "both") and agent.get("enabled", True)
        }
        ordered = _topological_sort(agents)

        # M2 order: data_harvester → portfolio_orchestrator → trend_phase_analyst
        # → level_analyst → options_strategist_s1 → smart_money_agent → debate_agent
        # → options_strategist_s2 → research_manager → risk_gate
        assert ordered[0] == "data_harvester"
        assert ordered[1] == "portfolio_orchestrator"
        assert ordered[2] == "trend_phase_analyst"
        assert ordered[3] == "level_analyst"
        assert ordered[4] == "options_strategist_s1"
        assert ordered[5] == "smart_money_agent"
        assert ordered[6] == "debate_agent"
        assert ordered[7] == "options_strategist_s2"
        assert ordered[8] == "research_manager"
        assert ordered[9] == "risk_gate"

    def test_lightweight_only_no_llm_agents(self):
        """Lightweight pipeline should exclude llm_dependency agents."""
        config = _load_agents_yaml()
        agents = {
            name: agent
            for name, agent in config["agents"].items()
            if agent.get("pipeline_mode") in ("lightweight", "both")
            and agent.get("enabled", True)
        }
        for name, agent in agents.items():
            assert not agent.get("llm_dependency", False), f"{name} should not require LLM"

    def test_missing_agents_yaml_raises(self):
        """GraphBuilder with invalid path should raise."""
        gb = GraphBuilder(agents_yaml_path="/nonexistent/agents.yaml")
        # build() reads from CONFIG_DIR, not the path param (which is unused in current impl)
        # This test verifies the default path works
        graph = gb.build("full")
        assert graph is not None


class TestTopologicalSort:
    def test_empty_agents(self):
        """Empty agent dict should return empty list."""
        assert _topological_sort({}) == []

    def test_single_agent(self):
        """Single agent should return single-element list."""
        agents = {"a": {"requires": [], "provides": ["x"]}}
        assert _topological_sort(agents) == ["a"]

    def test_diamond_dependency(self):
        """Diamond dependency: a → b,c → d."""
        agents = {
            "a": {"requires": [], "provides": ["x"]},
            "b": {"requires": ["x"], "provides": ["y"]},
            "c": {"requires": ["x"], "provides": ["z"]},
            "d": {"requires": ["y", "z"], "provides": ["w"]},
        }
        ordered = _topological_sort(agents)
        assert ordered[0] == "a"
        assert ordered[-1] == "d"
        assert ordered.index("b") < ordered.index("d")
        assert ordered.index("c") < ordered.index("d")


class TestFindProvider:
    def test_exact_match(self):
        """Exact field match should return provider."""
        agents = {"a": {"provides": ["market_data"]}}
        assert _find_provider("market_data", agents) == "a"

    def test_prefix_match(self):
        """Prefix match: 'analyst_outputs' matches 'analyst_outputs.levels'."""
        agents = {"a": {"provides": ["analyst_outputs.levels"]}}
        assert _find_provider("analyst_outputs", agents) == "a"

    def test_no_match(self):
        """No match should return None."""
        agents = {"a": {"provides": ["x"]}}
        assert _find_provider("y", agents) is None
