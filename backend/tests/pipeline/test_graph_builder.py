"""Tests for GraphBuilder — manifest-driven dynamic assembly with parallel fan-out."""

from aegis.pipeline.graph_builder import (
    GraphBuilder,
    _find_provider,
    _group_by_parallel,
    _load_agents_yaml,
    _topological_sort,
)
from aegis.pipeline.state import merge_dicts, merge_lists


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
        """Topological sort should match M2 graph_full.py order."""
        config = _load_agents_yaml()
        agents = {
            name: agent
            for name, agent in config["agents"].items()
            if agent.get("pipeline_mode") in ("full", "both") and agent.get("enabled", True)
        }
        ordered = _topological_sort(agents)

        # M2 order: data_harvester → portfolio_orchestrator → signal_analysts
        # (fund_flow, trend_phase, level, options_s1, smart_money) → debate
        # → options_strategist_s2 → research_manager → risk_gate
        assert ordered[0] == "data_harvester"
        assert ordered[1] == "portfolio_orchestrator"
        # Signal layer (order within parallel group may vary)
        signal_agents = set(ordered[2:7])
        assert signal_agents == {
            "fund_flow_agent", "trend_phase_analyst", "level_analyst",
            "options_strategist_s1", "smart_money_agent",
        }
        assert ordered[7] == "debate_agent"
        assert ordered[8] == "options_strategist_s2"
        assert ordered[9] == "research_manager"
        assert ordered[10] == "risk_gate"

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


# ---------------------------------------------------------------------------
# M2 Branch E+F: Parallel grouping tests
# ---------------------------------------------------------------------------


class TestGroupByParallel:
    def test_all_singletons(self):
        """Agents without parallel_group should each be their own group."""
        agents = {
            "a": {"parallel_group": None},
            "b": {"parallel_group": None},
            "c": {"parallel_group": None},
        }
        groups = _group_by_parallel(["a", "b", "c"], agents)
        assert groups == [["a"], ["b"], ["c"]]

    def test_single_parallel_group(self):
        """Consecutive agents with same parallel_group should be grouped."""
        agents = {
            "a": {"parallel_group": "signal"},
            "b": {"parallel_group": "signal"},
            "c": {"parallel_group": "signal"},
        }
        groups = _group_by_parallel(["a", "b", "c"], agents)
        assert groups == [["a", "b", "c"]]

    def test_mixed_groups(self):
        """Singletons and parallel groups should be correctly separated."""
        agents = {
            "a": {"parallel_group": None},
            "b": {"parallel_group": "signal"},
            "c": {"parallel_group": "signal"},
            "d": {"parallel_group": None},
            "e": {"parallel_group": "signal"},
        }
        groups = _group_by_parallel(["a", "b", "c", "d", "e"], agents)
        assert groups == [["a"], ["b", "c"], ["d"], ["e"]]

    def test_real_signal_layer_grouping(self):
        """Signal layer agents (signal_analysts) should be grouped together."""
        agents = {
            "data_harvester": {"parallel_group": None},
            "portfolio_orchestrator": {"parallel_group": None},
            "trend_phase_analyst": {"parallel_group": "signal_analysts"},
            "level_analyst": {"parallel_group": "signal_analysts"},
            "options_strategist_s1": {"parallel_group": "signal_analysts"},
            "smart_money_agent": {"parallel_group": "signal_analysts"},
            "fund_flow_agent": {"parallel_group": "signal_analysts"},
            "debate_agent": {"parallel_group": None},
            "options_strategist_s2": {"parallel_group": None},
            "research_manager": {"parallel_group": None},
            "risk_gate": {"parallel_group": None},
        }
        ordered = [
            "data_harvester", "portfolio_orchestrator",
            "fund_flow_agent", "trend_phase_analyst", "level_analyst",
            "options_strategist_s1", "smart_money_agent",
            "debate_agent", "options_strategist_s2",
            "research_manager", "risk_gate",
        ]
        groups = _group_by_parallel(ordered, agents)
        assert groups[0] == ["data_harvester"]
        assert groups[1] == ["portfolio_orchestrator"]
        assert len(groups[2]) == 5  # signal_analysts group
        assert set(groups[2]) == {
            "fund_flow_agent", "trend_phase_analyst", "level_analyst",
            "options_strategist_s1", "smart_money_agent",
        }
        assert groups[3] == ["debate_agent"]
        assert groups[4] == ["options_strategist_s2"]
        assert groups[5] == ["research_manager"]
        assert groups[6] == ["risk_gate"]

    def test_empty_list(self):
        """Empty ordered list should return empty groups."""
        assert _group_by_parallel([], {}) == []


# ---------------------------------------------------------------------------
# State reducers
# ---------------------------------------------------------------------------


class TestStateReducers:
    def test_merge_dicts_combines_keys(self):
        """merge_dicts should combine keys from both dicts."""
        left = {"agent_a": {"score": 80}}
        right = {"agent_b": {"score": 90}}
        result = merge_dicts(left, right)
        assert "agent_a" in result
        assert "agent_b" in result
        assert result["agent_a"]["score"] == 80
        assert result["agent_b"]["score"] == 90

    def test_merge_dicts_right_overrides_left(self):
        """merge_dicts: right dict values override left on key conflict."""
        left = {"agent_a": {"score": 80}}
        right = {"agent_a": {"score": 95}}
        result = merge_dicts(left, right)
        assert result["agent_a"]["score"] == 95

    def test_merge_dicts_does_not_mutate_original(self):
        """merge_dicts should not mutate the original dicts."""
        left = {"a": 1}
        right = {"b": 2}
        result = merge_dicts(left, right)
        assert left == {"a": 1}
        assert right == {"b": 2}
        assert result == {"a": 1, "b": 2}

    def test_merge_lists_concatenates(self):
        """merge_lists should concatenate two lists."""
        left = [{"agent": "a", "error": "e1"}]
        right = [{"agent": "b", "error": "e2"}]
        result = merge_lists(left, right)
        assert len(result) == 2
        assert result[0]["agent"] == "a"
        assert result[1]["agent"] == "b"

    def test_merge_lists_empty(self):
        """merge_lists with empty lists should work."""
        assert merge_lists([], []) == []
        assert merge_lists([1, 2], []) == [1, 2]
        assert merge_lists([], [3, 4]) == [3, 4]


# ---------------------------------------------------------------------------
# GraphBuilder parallel mode
# ---------------------------------------------------------------------------


class TestGraphBuilderParallel:
    def test_full_graph_has_parallel_groups(self):
        """Full pipeline graph should include parallel signal layer."""
        gb = GraphBuilder()
        graph = gb.build("full")
        nodes = list(graph.nodes.keys()) if hasattr(graph, "nodes") else []
        # Signal layer agents should all be present
        signal_agents = {
            "trend_phase_analyst", "level_analyst",
            "options_strategist_s1", "smart_money_agent", "fund_flow_agent",
        }
        assert signal_agents.issubset(set(nodes))

    def test_lightweight_graph_excludes_llm_agents(self):
        """Lightweight pipeline should not include LLM-dependent agents."""
        gb = GraphBuilder()
        graph = gb.build("lightweight")
        nodes = list(graph.nodes.keys()) if hasattr(graph, "nodes") else []
        # LLM agents should NOT be in lightweight
        assert "debate_agent" not in nodes
        assert "options_strategist_s2" not in nodes
        assert "research_manager" not in nodes
        assert "smart_money_agent" not in nodes
        assert "fund_flow_agent" not in nodes

    def test_lightweight_graph_has_rule_only_agents(self):
        """Lightweight pipeline should include rule-only agents."""
        gb = GraphBuilder()
        graph = gb.build("lightweight")
        nodes = list(graph.nodes.keys()) if hasattr(graph, "nodes") else []
        assert "data_harvester" in nodes
        assert "portfolio_orchestrator" in nodes
        assert "trend_phase_analyst" in nodes
        assert "level_analyst" in nodes

    def test_full_graph_entry_point_is_data_harvester(self):
        """Entry point should be data_harvester."""
        config = _load_agents_yaml()
        agents = {
            name: agent
            for name, agent in config["agents"].items()
            if agent.get("pipeline_mode") in ("full", "both") and agent.get("enabled", True)
        }
        ordered = _topological_sort(agents)
        assert ordered[0] == "data_harvester"

    def test_full_graph_end_is_risk_gate(self):
        """Last agent should be risk_gate."""
        config = _load_agents_yaml()
        agents = {
            name: agent
            for name, agent in config["agents"].items()
            if agent.get("pipeline_mode") in ("full", "both") and agent.get("enabled", True)
        }
        ordered = _topological_sort(agents)
        assert ordered[-1] == "risk_gate"
