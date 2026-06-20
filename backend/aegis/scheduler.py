"""APScheduler 常驻进程 — WeightAdapter + Memory compression/cleanup cron jobs.

Usage:
    uv run python -m aegis.scheduler
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aegis.llm.client import LLMClient
from aegis.memory.compressor import MemoryCompressor
from aegis.memory.long_term_store import LongTermStore
from aegis.memory.observation_period import ObservationPeriodManager
from aegis.memory.short_term_store import ShortTermStore
from aegis.memory.thesis_store import ThesisStore
from aegis.memory.vector_store import VectorStore
from aegis.memory.weight_adapter import WeightAdapter
from aegis.memory.weight_store import WeightStore
from aegis.utils.settings import settings

# ---------------------------------------------------------------------------
# Job functions
# ---------------------------------------------------------------------------


def _observation_check_job() -> None:
    """Daily check: has the observation period ended?"""
    logger.info("Scheduler: running observation_check_job")
    engine = create_engine(settings.DATABASE_URL)
    try:
        with Session(engine) as session:
            thesis_store = ThesisStore()
            weight_store = WeightStore()
            weight_adapter = WeightAdapter(weight_store, thesis_store)
            manager = ObservationPeriodManager(weight_store, thesis_store, weight_adapter)
            transitioned = manager.check_and_transition(session)
            if transitioned:
                logger.info("Scheduler: observation period transitioned → backfill complete")
            else:
                logger.info("Scheduler: observation period still active or already ended")
    except Exception:
        logger.exception("Scheduler: observation_check_job failed")
    finally:
        engine.dispose()


def _weight_update_job() -> None:
    """Weekly job: run WeightAdapter.update_weights."""
    logger.info("Scheduler: running weight_update_job")
    engine = create_engine(settings.DATABASE_URL)
    try:
        with Session(engine) as session:
            thesis_store = ThesisStore()
            weight_store = WeightStore()
            weight_adapter = WeightAdapter(weight_store, thesis_store)
            updated = weight_adapter.update_weights(session)
            if updated:
                logger.info(f"Scheduler: updated weights: {updated}")
            else:
                logger.info("Scheduler: no weights updated (insufficient samples or no change)")
    except Exception:
        logger.exception("Scheduler: weight_update_job failed")
    finally:
        engine.dispose()


def _memory_compression_job() -> None:
    """Daily job: compress old long-term memory records via LLM."""
    logger.info("Scheduler: running memory_compression_job")
    engine = create_engine(settings.DATABASE_URL)
    try:
        with Session(engine) as session:
            long_term = LongTermStore(lambda: session)
            vector = VectorStore(llm_client=LLMClient())
            llm_client = LLMClient()
            compressor = MemoryCompressor(long_term, vector, llm_client, _load_memory_config())
            stats = asyncio.get_event_loop().run_until_complete(compressor.run_compression())
            logger.info(f"Scheduler: compression complete: {stats}")
    except Exception:
        logger.exception("Scheduler: memory_compression_job failed")
    finally:
        engine.dispose()


def _short_term_cleanup_job() -> None:
    """Daily job: clean up expired short-term memory records."""
    logger.info("Scheduler: running short_term_cleanup_job")
    engine = create_engine(settings.DATABASE_URL)
    try:
        with Session(engine) as session:
            store = ShortTermStore(lambda: session)
            deleted = store.cleanup_expired()
            logger.info(f"Scheduler: cleaned up {deleted} expired short-term records")
    except Exception:
        logger.exception("Scheduler: short_term_cleanup_job failed")
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Scheduler factory
# ---------------------------------------------------------------------------


def _load_schedule_config() -> dict[str, Any]:
    config_path = Path(__file__).resolve().parent.parent / "config" / "schedule.yaml"
    with open(config_path) as f:
        return cast(dict[str, Any], yaml.safe_load(f))


def _load_memory_config() -> dict[str, Any]:
    config_path = Path(__file__).resolve().parent.parent / "config" / "memory.yaml"
    with open(config_path) as f:
        return cast(dict[str, Any], yaml.safe_load(f))


def create_scheduler() -> BackgroundScheduler:
    """Create and configure the APScheduler with weight adapter jobs.

    Returns:
        Configured BackgroundScheduler (not started).
    """
    scheduler = BackgroundScheduler()

    config = _load_schedule_config()
    wa_config = config.get("schedules", {}).get("weight_adapter", {})

    # Observation check — daily at 1:00 AM ET
    obs_cfg = wa_config.get("observation_check", {})
    obs_cron = obs_cfg.get("cron", "0 1 * * *")
    obs_tz = obs_cfg.get("timezone", "US/Eastern")
    scheduler.add_job(
        _observation_check_job,
        trigger=CronTrigger.from_crontab(obs_cron, timezone=obs_tz),
        id="observation_check",
        name="Observation period check",
        replace_existing=True,
    )
    logger.info(f"Scheduler: observation_check job registered (cron={obs_cron}, tz={obs_tz})")

    # Weight update — weekly Sunday at 4:00 AM ET
    wu_cfg = wa_config.get("weight_update", {})
    wu_cron = wu_cfg.get("cron", "0 4 * * 0")
    wu_tz = wu_cfg.get("timezone", "US/Eastern")
    scheduler.add_job(
        _weight_update_job,
        trigger=CronTrigger.from_crontab(wu_cron, timezone=wu_tz),
        id="weight_update",
        name="Weight update",
        replace_existing=True,
    )
    logger.info(f"Scheduler: weight_update job registered (cron={wu_cron}, tz={wu_tz})")

    # Memory compression — daily at 2:00 AM ET
    mem_cfg = config.get("schedules", {}).get("memory", {})
    comp_cfg = mem_cfg.get("compression", {})
    comp_cron = comp_cfg.get("cron", "0 2 * * *")
    comp_tz = comp_cfg.get("timezone", "US/Eastern")
    scheduler.add_job(
        _memory_compression_job,
        trigger=CronTrigger.from_crontab(comp_cron, timezone=comp_tz),
        id="memory_compression",
        name="Memory compression",
        replace_existing=True,
    )
    logger.info(f"Scheduler: memory_compression job registered (cron={comp_cron}, tz={comp_tz})")

    # Short-term cleanup — daily at 3:00 AM ET
    clean_cfg = mem_cfg.get("cleanup", {})
    clean_cron = clean_cfg.get("cron", "0 3 * * *")
    clean_tz = clean_cfg.get("timezone", "US/Eastern")
    scheduler.add_job(
        _short_term_cleanup_job,
        trigger=CronTrigger.from_crontab(clean_cron, timezone=clean_tz),
        id="short_term_cleanup",
        name="Short-term memory cleanup",
        replace_existing=True,
    )
    logger.info(f"Scheduler: short_term_cleanup job registered (cron={clean_cron}, tz={clean_tz})")

    return scheduler


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the scheduler and block forever."""
    logger.info("Aegis WeightAdapter Scheduler starting")
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started. Press Ctrl+C to exit.")

    try:
        # Keep the main thread alive
        import signal
        import sys

        def _shutdown(signum: int, frame: Any) -> None:
            logger.info("Scheduler shutting down...")
            scheduler.shutdown(wait=False)
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
        signal.pause()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
