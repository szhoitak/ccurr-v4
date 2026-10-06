import asyncio
from decimal import Decimal

import pytest

from runtime_slice.backtest import BacktestEngine
from runtime_slice.clock import VirtualClock
from runtime_slice.isolation import BacktestBoundary
from runtime_slice.registry import PluginRegistry
from runtime_slice.strategy import DeterministicStrategy, InMemoryContextBuilder


NOW = 1_700_000_000_000


def test_offline_backtest_boundary_uses_same_plugin_lifecycle(tmp_path):
    registry = PluginRegistry()
    registry.register(DeterministicStrategy)
    clock = VirtualClock(NOW, NOW + 600_000, 300_000)
    builder = InMemoryContextBuilder(clock, "backtest")
    engine = BacktestEngine(registry, BacktestBoundary(tmp_path))
    result = asyncio.run(engine.run("deterministic", {}, NOW, NOW + 600_000, builder))
    assert result.strategy_id == "deterministic"
    assert result.initial_balance == Decimal("10000")
    assert result.final_balance == result.initial_balance
    assert result.output_path is not None
    assert result.output_path.parent == tmp_path
    assert clock.is_finished() is True


def test_backtest_boundary_rejects_live_mode(tmp_path):
    with pytest.raises(ValueError):
        BacktestBoundary(tmp_path, production_execution=True)
