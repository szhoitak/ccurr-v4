from decimal import Decimal

from runtime_slice.clock import VirtualClock
from runtime_slice.step2 import Kline, Step2VolumeEvaluator


NOW = 1_700_000_000_000


def rows(timeframe: str, count: int, volume: Decimal | None = Decimal("10")):
    step = {"1d": 86_400_000, "4h": 14_400_000, "1h": 3_600_000}[timeframe]
    return [Kline(timeframe, NOW - step * (count - index), volume, True) for index in range(count)]


def evaluator():
    return Step2VolumeEvaluator(VirtualClock(NOW, NOW + 10_000))


def test_zero_denominator_is_skipped_without_substitution():
    current = Kline("4h", NOW, Decimal("10"), True)
    decision = evaluator().evaluate("BTC/USDT", "4h", current, rows("4h", 5, Decimal("0")), rows("4h", 15))
    assert decision.observation is None
    assert decision.reason == "zero_denominator"


def test_missing_volume_is_skipped():
    current = Kline("4h", NOW, None, True)
    decision = evaluator().evaluate("BTC/USDT", "4h", current, rows("4h", 5), rows("4h", 15))
    assert decision.reason == "missing_volume"


def test_missing_or_duplicate_slot_is_skipped():
    current = Kline("4h", NOW, Decimal("30"), True)
    history = rows("4h", 5)
    history[1] = history[0]
    decision = evaluator().evaluate("BTC/USDT", "4h", current, history, rows("4h", 15))
    assert decision.reason == "duplicate_slot"


def test_insufficient_samples_is_skipped():
    current = Kline("4h", NOW, Decimal("30"), True)
    decision = evaluator().evaluate("BTC/USDT", "4h", current, rows("4h", 4), rows("4h", 15))
    assert decision.reason == "insufficient_samples"


def test_open_4h_candle_is_skipped():
    current = Kline("4h", NOW, Decimal("30"), False)
    decision = evaluator().evaluate("BTC/USDT", "4h", current, rows("4h", 5), rows("4h", 15))
    assert decision.reason == "open_candle"


def test_1d_open_candle_is_preserved_as_observation():
    current = Kline("1d", NOW, Decimal("30"), False)
    decision = evaluator().evaluate("BTC/USDT", "1d", current, rows("1d", 5), rows("1d", 15))
    assert decision.observation is not None
    assert decision.observation.is_closed is False


def test_threshold_equality_uses_greater_equal_and_elapsed_clock():
    current = Kline("4h", NOW, Decimal("30"), True)
    decision = evaluator().evaluate("BTC/USDT", "4h", current, rows("4h", 5, Decimal("10")), rows("4h", 15, Decimal("15")))
    assert decision.observation is not None
    assert decision.observation.rvol_ma7 == Decimal("3")
    assert decision.observation.is_spike is True
    assert decision.observation.elapsed_ms == 0
