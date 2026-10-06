from __future__ import annotations

from typing import Any, Protocol

from .clock import Clock


class StrategyContext:
    def __init__(
        self,
        clickhouse_reader: Any,
        redis_client: Any,
        config_client: Any,
        strategy_id: str,
        clock: Clock,
    ) -> None:
        self._clickhouse = clickhouse_reader
        self._redis = redis_client
        self._config = config_client
        self._strategy_id = strategy_id
        self._clock = clock
        self._config_cache: dict[str, Any] = {}

    def now_ms(self) -> int:
        return self._clock.now_ms()

    @property
    def strategy_id(self) -> str:
        return self._strategy_id


class ContextBuilder(Protocol):
    def build(self, strategy_id: str) -> StrategyContext: ...
