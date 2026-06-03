"""Hello-world LangGraph: START → echo_node → END."""
from langgraph.graph import END, StateGraph

from aegis.pipeline.state import PipelineState


def echo_node(state: PipelineState) -> dict[str, object]:
    """Echo the tickers back into scratchpad."""
    return {
        "scratchpad": {
            **state.scratchpad,
            "echo": f"Hello from Aegis 2.0! Tickers: {state.tickers}",
        }
    }


def build_hello_graph() -> StateGraph[PipelineState]:
    """Build a minimal hello-world graph."""
    graph = StateGraph(PipelineState)
    graph.add_node("echo", echo_node)
    graph.set_entry_point("echo")
    graph.add_edge("echo", END)
    return graph
