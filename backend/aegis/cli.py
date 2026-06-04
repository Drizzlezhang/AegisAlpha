"""Aegis 2.0 CLI entry point (Typer)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
import yaml
from loguru import logger

app = typer.Typer(
    name="aegis",
    help="Aegis 2.0 — Personal US Stock/Options Trading Decision Assistant",
)


@app.command()
def run(
    ticker: str = typer.Option("QQQ", help="Ticker symbol to analyze"),
    mode: str = typer.Option(
        "pre-market", help="Pipeline mode: pre-market | post-market | lightweight"
    ),
) -> None:
    """Run the Aegis pipeline and send results to Telegram."""

    async def _run() -> None:
        from aegis.notifier.telegram import TelegramNotifier
        from aegis.pipeline.runner import run_full, run_lightweight

        if mode == "lightweight":
            state = await run_lightweight([ticker])
        else:
            state = await run_full(ticker, mode)  # type: ignore[arg-type]

        notifier = TelegramNotifier()
        await notifier.send(state)

        typer.echo(f"Pipeline complete. Pipeline ID: {state.pipeline_id}")
        if state.error_flags:
            typer.echo(f"Errors: {len(state.error_flags)}")

    asyncio.run(_run())


@app.command()
def schedule_start() -> None:
    """Start APScheduler with schedule.yaml cron jobs."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    schedule_path = Path(__file__).resolve().parent.parent / "config" / "schedule.yaml"

    if not schedule_path.exists():
        logger.error(f"schedule.yaml not found at {schedule_path}")
        typer.echo("Error: schedule.yaml not found", err=True)
        raise typer.Exit(code=1)

    try:
        with open(schedule_path) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        logger.error(f"Failed to parse schedule.yaml: {exc}")
        typer.echo(f"Error: invalid schedule.yaml — {exc}", err=True)
        raise typer.Exit(code=1) from exc

    schedules = config.get("schedules", {})

    async def _run_full_pre_market() -> None:
        from aegis.notifier.telegram import TelegramNotifier
        from aegis.pipeline.runner import run_full

        logger.info("Running full pre-market pipeline")
        state = await run_full("QQQ", "pre-market")
        await TelegramNotifier().send(state)

    async def _run_full_post_market() -> None:
        from aegis.notifier.telegram import TelegramNotifier
        from aegis.pipeline.runner import run_full

        logger.info("Running full post-market pipeline")
        state = await run_full("QQQ", "post-market")
        await TelegramNotifier().send(state)

    async def _run_lightweight() -> None:
        from aegis.notifier.telegram import TelegramNotifier
        from aegis.pipeline.runner import run_lightweight

        logger.info("Running lightweight pipeline")
        state = await run_lightweight(["QQQ"])
        await TelegramNotifier().send(state)

    scheduler = AsyncIOScheduler()

    full_pre = schedules.get("full_pipeline", {}).get("pre_market", {})
    if full_pre.get("enabled", False):
        scheduler.add_job(
            _run_full_pre_market,
            trigger=CronTrigger.from_crontab(
                full_pre["cron"], timezone=full_pre.get("timezone", "US/Eastern")
            ),
            id="full_pre_market",
            name="Full Pipeline Pre-Market",
        )

    full_post = schedules.get("full_pipeline", {}).get("post_market", {})
    if full_post.get("enabled", False):
        scheduler.add_job(
            _run_full_post_market,
            trigger=CronTrigger.from_crontab(
                full_post["cron"], timezone=full_post.get("timezone", "US/Eastern")
            ),
            id="full_post_market",
            name="Full Pipeline Post-Market",
        )

    lw_pre = schedules.get("lightweight_pipeline", {}).get("pre_market", {})
    if lw_pre.get("enabled", False):
        scheduler.add_job(
            _run_lightweight,
            trigger=CronTrigger.from_crontab(
                lw_pre["cron"], timezone=lw_pre.get("timezone", "US/Eastern")
            ),
            id="lightweight_pre_market",
            name="Lightweight Pipeline Pre-Market",
        )

    lw_post = schedules.get("lightweight_pipeline", {}).get("post_market", {})
    if lw_post.get("enabled", False):
        scheduler.add_job(
            _run_lightweight,
            trigger=CronTrigger.from_crontab(
                lw_post["cron"], timezone=lw_post.get("timezone", "US/Eastern")
            ),
            id="lightweight_post_market",
            name="Lightweight Pipeline Post-Market",
        )

    trigger_cfg = schedules.get("trigger_check", {})
    if trigger_cfg.get("enabled", False):
        scheduler.add_job(
            _run_lightweight,
            trigger=CronTrigger.from_crontab(
                trigger_cfg.get("cron", "0 * * * *"),
                timezone=trigger_cfg.get("timezone", "US/Eastern"),
            ),
            id="trigger_check",
            name="Trigger Check",
        )

    scheduler.start()
    typer.echo("Scheduler started. Press Ctrl+C to stop.")
    logger.info("APScheduler started with cron jobs from schedule.yaml")

    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        typer.echo("Scheduler stopped.")


@app.command()
def health() -> None:
    """Check tool connectivity and configuration status."""

    async def _check() -> None:
        from aegis.utils.settings import settings

        typer.echo("=== Aegis 2.0 Health Check ===\n")

        # LLM
        typer.echo(f"LLM Base URL: {settings.LLM_BASE_URL}")
        typer.echo(f"LLM Model: {settings.LLM_MODEL_PRIMARY} / {settings.LLM_MODEL_MINI}")
        typer.echo(f"LLM API Key: {'configured' if settings.LLM_API_KEY else 'MISSING'}")

        # Telegram
        typer.echo(
            f"Telegram Bot Token: {'configured' if settings.TELEGRAM_BOT_TOKEN else 'MISSING'}"
        )
        typer.echo(f"Telegram Chat ID: {'configured' if settings.TELEGRAM_CHAT_ID else 'MISSING'}")

        # Data sources
        typer.echo(f"FRED API Key: {'configured' if settings.FRED_API_KEY else 'MISSING'}")
        typer.echo(f"Tavily API Key: {'configured' if settings.TAVILY_API_KEY else 'MISSING'}")
        typer.echo(
            f"Alpha Vantage API Key:"
            f" {'configured' if settings.ALPHA_VANTAGE_API_KEY else 'MISSING'}"
        )

        # Database
        typer.echo(f"Database URL: {settings.DATABASE_URL}")

        # Config files
        config_dir = Path(__file__).resolve().parent.parent / "config"
        for cfg_file in ["agents.yaml", "schedule.yaml", "tools.yaml", "rules.yaml"]:
            exists = (config_dir / cfg_file).exists()
            typer.echo(f"Config {cfg_file}: {'OK' if exists else 'MISSING'}")

        typer.echo("\nHealth check complete.")

    asyncio.run(_check())


@app.command()
def version() -> None:
    """Show version info."""
    typer.echo("Aegis 2.0 v0.1.0")


if __name__ == "__main__":
    app()
