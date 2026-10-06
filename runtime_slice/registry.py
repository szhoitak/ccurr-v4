from __future__ import annotations

from typing import Type

from .strategy import BaseStrategy


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, Type[BaseStrategy]] = {}

    def register(self, plugin: Type[BaseStrategy]) -> None:
        if not issubclass(plugin, BaseStrategy):
            raise TypeError("plugin must inherit BaseStrategy")
        strategy_id = plugin.strategy_id
        if strategy_id in self._plugins:
            raise ValueError(f"duplicate strategy_id: {strategy_id}")
        self._plugins[strategy_id] = plugin

    def unregister(self, strategy_id: str) -> None:
        self._plugins.pop(strategy_id, None)

    def get(self, strategy_id: str) -> Type[BaseStrategy]:
        try:
            return self._plugins[strategy_id]
        except KeyError as exc:
            raise KeyError(f"unknown strategy_id: {strategy_id}") from exc

    def list_all(self) -> list[Type[BaseStrategy]]:
        return list(self._plugins.values())

    def list_ids(self) -> list[str]:
        return list(self._plugins)
