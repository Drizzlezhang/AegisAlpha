"""Manifest-driven dynamic graph assembly for M2+.

Reads agents.yaml, filters by pipeline_mode, derives dependency order,
groups agents by parallel_group for concurrent execution via asyncio.gather,
and assembles a compiled StateGraph.

M2 Branch E+F: parallel execution for signal layer agents via composite nodes.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
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
    for concurrent execution. Agents without a parallel_group are singleton groups.
    """
    groups: list[list[str]] = []
    current_group: list[str] = []
    current_pg: str | None = None

    for name in ordered:
        agent = agents.get(name, {})
        pg = agent.get("parallel_group") or None

        if pg is None:
            if current_group:
                groups.append(current_group)
                current_group = []
                current_pg = None
            groups.append([name])
        elif pg == current_pg:
            current_group.append(name)
        else:
            if current_group:
                groups.append(current_group)
            current_group = [name]
            current_pg = pg

    if current_group:
        groups.append(current_group)

    return groups


class GraphBuilder:
    """Manifest-driven dynamic graph assembly with parallel execution.

    Reads agents.yaml, groups agents by parallel_group, and uses
    asyncio.gather within composite nodes for concurrent execution.
    Annotated state reducers (merge_dicts, merge_lists) handle
    conflict-free parallel writes to extensions, error_flags, and agent_timings.
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
            Compiled StateGraph with parallel execution for signal layer.
        """
        config = _load_agents_yaml()
        all_agents: dict[str, dict[str, Any]] = config.get("agents", {})

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

        ordered = _topological_sort(filtered)
        logger.info(f"GraphBuilder: {pipeline_mode} order = {ordered}")

        groups = _group_by_parallel(ordered, filtered)
        logger.info(
            f"GraphBuilder: {pipeline_mode} groups = "
            f"{[[g] if len(g)==1 else g for g in groups]}"
        )

        graph = StateGraph(PipelineState)

        # Add nodes: singleton agents get individual nodes,
        # parallel groups get composite nodes
        node_names: list[str] = []
        for group in groups:
            if len(group) == 1:
                name = group[0]
                graph.add_node(name, self._make_node(name))  # type: ignore[call-overload]
                node_names.append(name)
            else:
                # Composite node for parallel group
                composite_name = f"parallel_{group[0]}"
                graph.add_node(composite_name, self._make_composite_node(group))  # type: ignore[call-overload]
                node_names.append(composite_name)

        # Sequential edges between groups
        graph.set_entry_point(node_names[0])
        for i in range(len(node_names) - 1):
            graph.add_edge(node_names[i], node_names[i + 1])
        graph.add_edge(node_names[-1], END)

        return graph.compile()

    def _make_composite_node(
        self, agent_names: list[str]
    ) -> Callable[[PipelineState], Any]:
        """Create a node that runs multiple agents concurrently via asyncio.gather."""

        async def composite_fn(state: PipelineState) -> dict[str, Any]:
            async def run_one(name: str) -> None:
                node_fn = self._make_node(name)
                await node_fn(state)

            t0 = time.monotonic()
            results = await asyncio.gather(
                *[run_one(name) for name in agent_names],
                return_exceptions=True,
            )
            elapsed = time.monotonic() - t0

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"[{agent_names[i]}] parallel failed: {result}"
                    )
                    state.error_flags.append(
                        {"agent": agent_names[i], "error": str(result)}
                    )

            state.agent_timings[f"parallel_group"] = elapsed

            return {
                "extensions": state.extensions,
                "error_flags": state.error_flags,
                "agent_timings": state.agent_timings,
            }

        return composite_fn

    def _make_node(self, agent_name: str) -> Callable[[PipelineState], Any]:
        """Create a LangGraph node function for an agent."""

        async def node_fn(state: PipelineState) -> dict[str, Any]:
            import importlib

            # Map agent name to module path
            if agent_name.endswith("_agent"):
                module_name = f"aegis.agents.{agent_name}"
            else:
                module_name = f"aegis.agents.{agent_name}_agent"
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                logger.error(f"Agent module not found: {module_name}")
                state.error_flags.append(
                    {"agent": agent_name, "error": f"Module not found: {module_name}"}
                )
                return {
                    "extensions": state.extensions,
                    "error_flags": state.error_flags,
                    "agent_timings": state.agent_timings,
                }

            # Find the agent class
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
                return {
                    "extensions": state.extensions,
                    "error_flags": state.error_flags,
                    "agent_timings": state.agent_timings,
                }

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

            return {
                "extensions": result.extensions,
                "error_flags": result.error_flags,
                "agent_timings": result.agent_timings,
            }

        return node_fn
