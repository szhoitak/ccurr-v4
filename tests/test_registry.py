import asyncio

import pytest

from runtime_slice.registry import PluginRegistry
from runtime_slice.strategy import DeterministicStrategy


class AlternateStrategy(DeterministicStrategy):
    strategy_id = "alternate"


def test_registry_crud_and_duplicate_rejection():
    registry = PluginRegistry()
    registry.register(DeterministicStrategy)
    registry.register(AlternateStrategy)
    assert registry.list_ids() == ["deterministic", "alternate"]
    assert registry.get("deterministic") is DeterministicStrategy
    registry.unregister("alternate")
    assert registry.list_ids() == ["deterministic"]
    with pytest.raises(ValueError):
        registry.register(DeterministicStrategy)
    with pytest.raises(KeyError):
        registry.get("missing")


def test_registry_rejects_non_strategy():
    with pytest.raises(TypeError):
        PluginRegistry().register(object)
