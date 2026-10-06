from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .clock import Clock
from .context import StrategyContext
from .models import Candidate, Signal


class InMemoryContextBuilder:
    """Live/backtest-shaped builder using only injected in-memory dependencies."""

    def __init__(self, clock: Clock, mode: str) -> None:
        self.clock = clock
        self.mode = mode
        self.built_ids: list[str] = []

    def build(self, strategy_id: str) -> StrategyContext:
        self.built_ids.append(strategy_id)
        return StrategyContext(object(), object(), object(), strategy_id, self.clock)


class BaseStrategy(ABC):
    strategy_id = "base"
    strategy_name = "Base Strategy"
    version = "1.0"
    description = ""

    def __init__(self, config: dict[str, Any], context_builder: InMemoryContextBuilder) -> None:
        self._config = dict(config)
        self._context_builder = context_builder
        self._context: StrategyContext | None = None
        self.events: list[str] = []

    @classmethod
    @abstractmethod
    def get_default_config(cls) -> dict[str, Any]: ...

    def validate_config(self) -> bool:
        return True

    @property
    def context(self) -> StrategyContext:
        if self._context is None:
            raise RuntimeError("context is not built")
        return self._context

    async def on_start(self, context: StrategyContext) -> None:
        self._context = context
        self.events.append("on_start")

    @abstractmethod
    async def scan(self) -> list[Candidate]: ...

    async def evaluate(self, candidate: Candidate) -> Signal | None:
        self.events.append("evaluate")
        return None

    async def on_stop(self) -> None:
        self.events.append("on_stop")

    async def run_once(self) -> list[Candidate]:
        if not self.validate_config():
            raise ValueError("invalid strategy config")
        self.events.append("validate_config")
        self._context = self._context_builder.build(self.strategy_id)
        self.events.append("build_context")
        await self.on_start(self._context)
        candidates = await self.scan()
        for candidate in candidates:
            await self.evaluate(candidate)
        await self.on_stop()
        return candidates


class DeterministicStrategy(BaseStrategy):
    strategy_id = "deterministic"

    @classmethod
    def get_default_config(cls) -> dict[str, Any]:
        return {"enabled": True}

    async def scan(self) -> list[Candidate]:
        self.events.append("scan")
        return []
