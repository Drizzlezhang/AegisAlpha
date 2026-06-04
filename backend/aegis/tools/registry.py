"""Tool Registry — YAML-driven tool loading with Proxy pattern.

The ToolRegistry loads tool configurations from tools.yaml, instantiates adapters
with CircuitBreaker + RateLimiter + Cache, and returns ToolProxy instances that
inject cross-cutting concerns (CB → RL → Cache → Fallback) around fetch() calls.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, Field

from aegis.tools.base import BaseTool, ToolResult
from aegis.tools.cache import ToolCache
from aegis.tools.rate_limiter import AsyncTokenBucket
from aegis.utils.circuit_breaker import CircuitBreaker


class ToolRateLimitConfig(BaseModel):
    max_calls: int
    period: int  # seconds


class ToolCircuitBreakerConfig(BaseModel):
    failure_threshold: int = 3
    recovery_timeout: int = 120  # seconds


class ToolEntry(BaseModel):
    model_config = {"populate_by_name": True}

    name: str
    class_path: str = Field(alias="class")
    category: str
    tags: list[str] = []
    rate_limit: ToolRateLimitConfig | None = None
    circuit_breaker: ToolCircuitBreakerConfig | None = None
    fallback: str | None = None
    bound_agents: list[str] = []


class ToolsConfig(BaseModel):
    categories: list[str] = []
    tools: list[ToolEntry] = []

    @classmethod
    def from_yaml(cls, path: str | Path) -> ToolsConfig:
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)


class ToolProxy:
    """Wraps a BaseTool with CB/RL/Cache/Fallback cross-cutting concerns."""

    def __init__(
        self,
        adapter: BaseTool,
        entry: ToolEntry,
        circuit_breaker: CircuitBreaker | None,
        rate_limiter: AsyncTokenBucket | None,
        cache: ToolCache | None,
        fallback_proxy: ToolProxy | None = None,
    ) -> None:
        self._adapter = adapter
        self._entry = entry
        self._cb = circuit_breaker
        self._rl = rate_limiter
        self._cache = cache
        self._fallback = fallback_proxy

    @property
    def name(self) -> str:
        return self._entry.name

    @property
    def tags(self) -> list[str]:
        return self._entry.tags

    @property
    def category(self) -> str:
        return self._entry.category

    async def fetch(self, **kwargs: Any) -> ToolResult:
        # 1. Circuit Breaker check
        if self._cb is not None and not self._cb.allow_request():
            logger.warning(f"Circuit breaker OPEN for {self.name}")
            return ToolResult(
                success=False,
                error=f"Circuit breaker open for {self.name}",
                source=self.name,
            )

        # 2. Rate Limiter
        if self._rl is not None:
            await self._rl.acquire()

        # 3. Cache check
        if self._cache is not None:
            cache_key = self._build_cache_key(**kwargs)
            cached = await self._cache.get(self.name, cache_key)
            if cached is not None:
                return cached

        # 4. Execute adapter
        try:
            result = await self._adapter.fetch(**kwargs)
        except Exception as e:
            logger.warning(f"Tool {self.name} failed: {e}")
            result = ToolResult(success=False, error=str(e), source=self.name)

        # 5. Record CB state
        if self._cb is not None:
            if result.success:
                self._cb.record_success()
            else:
                self._cb.record_failure()

        # 6. Fallback on failure
        if not result.success and self._fallback is not None:
            logger.warning(f"Falling back from {self.name} to {self._fallback.name}")
            return await self._fallback.fetch(**kwargs)

        # 7. Cache successful result
        if result.success and self._cache is not None:
            cache_key = self._build_cache_key(**kwargs)
            await self._cache.set(self.name, cache_key, result)

        return result

    def _build_cache_key(self, **kwargs: Any) -> str:
        """Build a deterministic cache key from kwargs."""
        parts = [f"{k}={v}" for k, v in sorted(kwargs.items())]
        return "_".join(parts) if parts else "default"


class ToolRegistry:
    """Central registry for all tool adapters."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolProxy] = {}
        self._by_tag: dict[str, list[ToolProxy]] = {}

    @classmethod
    def load_from_yaml(cls, path: str | Path, cache_dir: str = "data/cache") -> ToolRegistry:
        """Load and instantiate all tools from a YAML config file."""
        config = ToolsConfig.from_yaml(path)
        registry = cls()
        cache = ToolCache(cache_dir)

        # Phase 1: Instantiate all adapters (without fallback wiring)
        proxies: dict[str, ToolProxy] = {}
        for entry in config.tools:
            adapter = registry._instantiate_adapter(entry.class_path)

            cb = None
            if entry.circuit_breaker is not None:
                cb = CircuitBreaker(
                    name=entry.name,
                    failure_threshold=entry.circuit_breaker.failure_threshold,
                    recovery_timeout_sec=entry.circuit_breaker.recovery_timeout,
                )

            rl = None
            if entry.rate_limit is not None:
                rl = AsyncTokenBucket(
                    max_tokens=entry.rate_limit.max_calls,
                    period_sec=entry.rate_limit.period,
                )

            proxies[entry.name] = ToolProxy(
                adapter=adapter,
                entry=entry,
                circuit_breaker=cb,
                rate_limiter=rl,
                cache=cache,
                fallback_proxy=None,  # Wired in phase 2
            )

        # Phase 2: Wire fallback references
        for entry in config.tools:
            if entry.fallback and entry.fallback in proxies:
                proxy = proxies[entry.name]
                proxy._fallback = proxies[entry.fallback]

        # Register all proxies
        for entry in config.tools:
            proxy = proxies[entry.name]
            registry._tools[entry.name] = proxy
            for tag in entry.tags:
                registry._by_tag.setdefault(tag, []).append(proxy)

        logger.info(f"ToolRegistry loaded {len(registry._tools)} tools from {path}")
        return registry

    @staticmethod
    def _instantiate_adapter(class_path: str) -> BaseTool:
        """Dynamically import and instantiate an adapter class."""
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        cls: type[BaseTool] = getattr(module, class_name)
        return cls()

    def get(self, name: str) -> ToolProxy:
        """Get a tool proxy by name."""
        if name not in self._tools:
            available = list(self._tools.keys())
            raise KeyError(f"Tool '{name}' not found in registry. Available: {available}")
        return self._tools[name]

    def register(
        self, name: str, tool: BaseTool, config: dict[str, Any] | None = None
    ) -> None:
        """Programmatically register a tool (for testing / dynamic plugins).

        Args:
            name: Unique tool name.
            tool: BaseTool instance.
            config: Optional dict with keys: tags, rate_limit, circuit_breaker.
        """
        cfg = config or {}
        tags: list[str] = cfg.get("tags", [])
        rl_cfg = cfg.get("rate_limit")
        cb_cfg = cfg.get("circuit_breaker")

        rl = None
        if rl_cfg:
            rl = AsyncTokenBucket(
                max_tokens=rl_cfg.get("max_calls", 5),
                period_sec=rl_cfg.get("period", 60),
            )

        cb = None
        if cb_cfg:
            cb = CircuitBreaker(
                name=name,
                failure_threshold=cb_cfg.get("failure_threshold", 3),
                recovery_timeout_sec=cb_cfg.get("recovery_timeout", 120),
            )

        entry = ToolEntry(
            name=name,
            class_path=f"{tool.__class__.__module__}.{tool.__class__.__name__}",
            category=cfg.get("category", "unknown"),
            tags=tags,
        )

        proxy = ToolProxy(
            adapter=tool,
            entry=entry,
            circuit_breaker=cb,
            rate_limiter=rl,
            cache=None,
        )
        self._tools[name] = proxy
        for tag in tags:
            self._by_tag.setdefault(tag, []).append(proxy)
        logger.info(f"ToolRegistry: registered '{name}' with tags={tags}")

    def find_by_tag(self, tag: str) -> list[ToolProxy]:
        """Find all tools matching a given tag."""
        return self._by_tag.get(tag, [])

    def list_all(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
