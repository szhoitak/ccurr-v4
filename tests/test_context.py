from runtime_slice.clock import VirtualClock
from runtime_slice.context import StrategyContext


def test_context_delegates_time_and_keeps_strategy_id():
    clock = VirtualClock(1_700_000_000_000, 1_700_000_001_000)
    context = StrategyContext(object(), object(), object(), "demo", clock)
    assert context.now_ms() == clock.now_ms()
    assert context.strategy_id == "demo"
