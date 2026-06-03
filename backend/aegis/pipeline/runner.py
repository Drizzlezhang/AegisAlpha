"""Pipeline runner entry point."""
from aegis.pipeline.graph import build_hello_graph
from aegis.pipeline.state import PipelineState


async def run_pipeline(tickers: list[str] | None = None) -> PipelineState:
    """Run the hello-world pipeline.

    Args:
        tickers: List of ticker symbols to process.

    Returns:
        The final PipelineState after graph execution.
    """
    state = PipelineState(
        pipeline_id="hello-world-001",
        mode="manual",
        tickers=tickers or ["QQQ"],
    )
    graph = build_hello_graph()
    app = graph.compile()
    result = await app.ainvoke(state)
    return PipelineState(**result)
