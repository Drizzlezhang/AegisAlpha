"""Logging configuration using loguru."""
import sys

from loguru import logger


def setup_logging() -> None:
    """Configure loguru for Aegis 2.0."""
    logger.remove()
    fmt_stderr = (
        "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(sys.stderr, format=fmt_stderr, level="INFO", colorize=True)
    fmt_file = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{name}:{function}:{line} - {message}"
    )
    logger.add(
        "data/logs/aegis_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        format=fmt_file,
    )


__all__ = ["logger", "setup_logging"]
