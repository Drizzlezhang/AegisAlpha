"""Manifest-driven dynamic graph assembly for M2+.

Reads agents.yaml, filters by pipeline_mode, derives dependency order,
groups agents by parallel_group for fan-out/fan-in, and assembles a
compiled StateGraph with Annotated state reducers for parallel writes.

M2 Branch E+F: parallel fan-out/fan-in for signal layer agents.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send
from loguru import logger

from aegis.pipeline.state import PipelineState

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def _load_agents_yaml() -> dict[str, Any]:
    path = CONFIG_DIR / "agents.yaml"
    if not path.exists():
        raise FileNotFoundError(f"agents.yaml not found at {path}")
    with open(path) as f:
        return dict(yaml.safe_load(f))


def _topological_sort(
    agents: dict[str, dict[str, Any]],
) -> list[str]:
    """Derive execution order from requires/provides dependencies.

    Simple approach: sort by dependency depth (number of transitive requires).
    Agents with no requires go first; agents that require outputs of others go later.
    """
    agent_names = list(agents.keys())

    # Compute dependency depth via BFS
    def depth(name: str, visited: set[str] | None = None) -> int:
        if visited is None:
            visited = set()
        if name in visited:
            return 0
        visited.add(name)
        agent = agents.get(name, {})
        requires = agent.get("requires", [])
        max_d = 0
        for req in requires:
            provider = _find_provider(req, agents)
            if provider and provider != name:
                max_d = max(max_d, depth(provider, visited) + 1)
        return max_d

    # Sort by depth ascending
    sorted_names = sorted(agent_names, key=lambda n: depth(n))
    return sorted_names


def _find_provider(
    field: str, agents: dict[str, dict[str, Any]]
) -> str | None:
    """Find which agent provides a given field.

    Supports prefix matching: "analyst_outputs" matches "analyst_outputs.trend_phase".
    """
    for name, agent in agents.items():
        provides = agent.get("provides", [])
        for p in provides:
            if p == field or p.startswith(field + "."):
                return name
    return None


def _group_by_parallel(
    ordered: list[str], agents: dict[str, dict[str, Any]]
) -> list[list[str]]:
    """Group topologically sorted agents by parallel_group.

    Consecutive agents sharing the same parallel_group are grouped together
    for fan-out/fan-in. Agents without a parallel_group are singleton groups.
    """
    groups: list[list[str]] = []
    current_group: list[str] = []
    current_pg: str | None = None

    for name in ordered:
        agent = agents.get(name, {})
        pg = agent.get("parallel_group") or None

        if pg is None:
            # Singleton: flush current group, add as solo
            if current_group:
                groups.append(current_group)
                current_group = []
                current_pg = None
            groups.append([name])
        elif pg == current_pg:
            # Same parallel group, continue
            current_group.append(name)
        else:
            # New parallel group: flush old, start new
            if current_group:
                groups.append(current_group)
            current_group = [name]
            current_pg = pg

    if current_group:
        groups.append(current_group)

    return groups


class GraphBuilder:
    """Manifest-driven dynamic graph assembly with parallel fan-out/fan-in.

    Reads agents.yaml, groups agents by parallel_group, and uses LangGraph
    Send-based fan-out for parallel execution. Annotated state reducers
    (merge_dicts, merge_lists) handle conflict-free parallel writes to
    extensions, error_flags, and agent_timings.
    """

    def __init__(self, agents_yaml_path: str | None = None) -> None:
        self._agents_yaml_path = agents_yaml_path

    def build(
        self, pipeline_mode: str
    ) -> CompiledStateGraph[PipelineState, None, PipelineState, PipelineState]:
        """Build a compiled StateGraph from agents.yaml.

        Args:
            pipeline_mode: "full" or "lightweight"

        Returns:
            Compiled StateGraph with parallel fan-out/fan-in for signal layer.
        """
        config = _load_agents_yaml()
        all_agents: dict[str, dict[str, Any]] = config.get("agents", {})

        # Filter by pipeline_mode
        if pipeline_mode == "lightweight":
            filtered = {
                name: agent
                for name, agent in all_agents.items()
                if agent.get("pipeline_mode") in ("lightweight", "both")
                and agent.get("enabled", True)
            }
        else:
            filtered = {
                name: agent
                for name, agent in all_agents.items()
                if agent.get("pipeline_mode") in ("full", "both")
                and agent.get("enabled", True)
            }

        if not filtered:
            logger.warning(f"No agents found for pipeline_mode={pipeline_mode}")
            return StateGraph(PipelineState).compile()

        # Topological sort
        ordered = _topological_sort(filtered)
        logger.info(f"GraphBuilder: {pipeline_mode} order = {ordered}")

        # Group by parallel_group for fan-out/fan-in
        groups = _group_by_parallel(ordered, filtered)
        logger.info(f"GraphBuilder: {pipeline_mode} groups = {[[g] if len(g)==1 else g for g in groups]}")

        # Build graph
        graph = StateGraph(PipelineState)

        # Add all nodes
        for agent_name in ordered:
            graph.add_node(agent_name, self._make_node(agent_name))  # type: ignore[call-overload]

        # Set entry point (first agent in first group)
        graph.set_entry_point(groups[0][0])

        # Add edges with parallel fan-out/fan-in
        for i, group in enumerate(groups):
            is_last = (i == len(groups) - 1)

            if is_last:
                # Last group → END
                for name in group:
                    graph.add_edge(name, END)
            else:
                next_group = groups[i + 1]
                next_first = next_group[0]

                if len(group) == 1 and len(next_group) == 1:
                    # Sequential: single → single
                    graph.add_edge(group[0], next_group[0])
                elif len(group) == 1 and len(next_group) > 1:
                    # Fan-out: single → parallel group (using Send)
                    graph.add_conditional_edges(
                        group[0],
                        self._fan_out(next_group),
                        {name: name for name in next_group},
                    )
                elif len(group) > 1 and len(next_group) == 1:
                    # Fan-in: parallel group → single
                    for name in group:
                        graph.add_edge(name, next_group[0])
                else:
                    # Parallel → parallel: fan-in then fan-out
                    # Use a synthetic join node? For now, fan-in to next_group[0]
                    # then fan-out from there. But this shouldn't happen in practice.
                    for name in group:
                        graph.add_edge(name, next_group[0])

        return graph.compile()

    @staticmethod
    def _fan_out(targets: list[str]) -> Callable[[PipelineState], list[Send]]:
        """Create a fan-out router that sends state to all target agents in parallel."""

        def router(state: PipelineState) -> list[Send]:
            return [Send(target, state.model_dump()) for target in targets]

        return router

    def _make_node(self, agent_name: str) -> Callable[[PipelineState], Any]:
        """Create a LangGraph node function for an agent."""

        async def node_fn(state: PipelineState) -> dict[str, Any]:
            import importlib

            # Map agent name to module path (convention: aegis.agents.{name}_agent)
            module_name = f"aegis.agents.{agent_name}_agent"
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                logger.error(f"Agent module not found: {module_name}")
                state.error_flags.append(
                    {"agent": agent_name, "error": f"Module not found: {module_name}"}
                )
                return dict(state.model_dump())

            # Find the agent class (convention: PascalCase with Agent suffix)
            agent_cls = None
            for attr_name in dir(module):
                if attr_name.endswith("Agent") and not attr_name.startswith("Base"):
                    candidate = getattr(module, attr_name)
                    if hasattr(candidate, "manifest") and hasattr(candidate, "run"):
                        agent_cls = candidate
                        break

            if agent_cls is None:
                logger.error(f"Agent class not found in {module_name}")
                state.error_flags.append(
                    {"agent": agent_name, "error": "Agent class not found"}
                )
                return dict(state.model_dump())

            agent = agent_cls(memory={}, tools={}, config={})
            t0 = time.monotonic()
            try:
                result = await agent.run(state)
            except Exception as exc:
                logger.exception(f"[{agent_name}] failed: {exc}")
                state.error_flags.append({"agent": agent_name, "error": str(exc)})
                result = state
            elapsed = time.monotonic() - t0
            result.agent_timings[agent_name] = elapsed
            return dict(result.model_dump())

        return node_fn
