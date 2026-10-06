import asyncio

from runtime_slice.clock import VirtualClock
from runtime_slice.strategy import DeterministicStrategy, InMemoryContextBuilder


NOW = 1_700_000_000_000


def test_strategy_uses_canonical_constructor_and_lifecycle_order():
    builder = InMemoryContextBuilder(VirtualClock(NOW, NOW + 1000), "live")
    strategy = DeterministicStrategy({}, builder)
    asyncio.run(strategy.run_once())
    assert strategy.events == ["validate_config", "build_context", "on_start", "scan", "on_stop"]
    assert builder.built_ids == ["deterministic"]
    assert strategy.context.strategy_id == "deterministic"


def test_live_and_backtest_builders_have_same_strategy_facing_result():
    live_builder = InMemoryContextBuilder(VirtualClock(NOW, NOW + 1000), "live")
    backtest_builder = InMemoryContextBuilder(VirtualClock(NOW, NOW + 1000), "backtest")
    live = DeterministicStrategy({}, live_builder)
    backtest = DeterministicStrategy({}, backtest_builder)
    assert asyncio.run(live.run_once()) == asyncio.run(backtest.run_once()) == []
    assert live.events == backtest.events
    assert live.context.now_ms() == backtest.context.now_ms() == NOW
