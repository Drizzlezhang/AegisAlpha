"""Dependency injection for FastAPI routes."""

from aegis.utils.settings import Settings, settings


def get_settings() -> Settings:
    return settings
