"""Aegis 2.0 CLI entry point (Typer)."""
import typer

app = typer.Typer(
    name="aegis",
    help="Aegis 2.0 — Personal US Stock/Options Trading Decision Assistant",
)


@app.command()
def run(
    ticker: str = typer.Option("QQQ", help="Ticker symbol to analyze"),
    mode: str = typer.Option("manual", help="Pipeline mode: pre-market, post-market, manual"),
) -> None:
    """Run the Aegis pipeline for a given ticker."""
    typer.echo(f"Aegis 2.0 — Running pipeline for {ticker} in {mode} mode")


@app.command()
def version() -> None:
    """Show version info."""
    typer.echo("Aegis 2.0 v0.1.0")


if __name__ == "__main__":
    app()
