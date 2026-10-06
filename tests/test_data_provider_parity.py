from decimal import Decimal

from runtime_slice.clock import VirtualClock
from runtime_slice.data_provider import HistoricalDataProvider
from runtime_slice.step2 import Kline, Step2VolumeEvaluator


NOW = 1_700_000_000_000


def make_rows(count=20, timeframe="4h"):
    step = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}[timeframe]
    return [Kline(timeframe, NOW - step * (count - i), Decimal("10"), True) for i in range(count)]


def test_provider_preload_limit_and_range_are_deterministic():
    provider = HistoricalDataProvider()
    rows = make_rows()
    provider.preload("BTC/USDT", "4h", rows)
    assert provider.get_klines_at("BTC/USDT", "4h", NOW, 3) == rows[-3:]
    assert provider.get_kline_at("BTC/USDT", "4h", NOW).slot_ts == rows[-1].slot_ts
    assert provider.get_range("BTC/USDT", "4h", rows[5].slot_ts, rows[8].slot_ts) == rows[5:9]


def test_provider_preserves_missing_slots_without_fabrication():
    provider = HistoricalDataProvider()
    rows = make_rows()
    provider.preload("BTC/USDT", "4h", rows[::2])
    result = provider.get_range("BTC/USDT", "4h", rows[0].slot_ts, rows[-1].slot_ts)
    assert len(result) == len(rows[::2])
    assert [item.slot_ts for item in result] == [item.slot_ts for item in rows[::2]]


def test_step2_direct_rows_and_provider_rows_have_same_result():
    rows = make_rows()
    current = Kline("4h", NOW, Decimal("30"), True)
    evaluator = Step2VolumeEvaluator(VirtualClock(NOW, NOW + 1000))
    direct = evaluator.evaluate("BTC/USDT", "4h", current, rows[:5], rows[:15])
    provider = HistoricalDataProvider()
    provider.preload("BTC/USDT", "4h", rows)
    from_provider = evaluator.evaluate(
        "BTC/USDT", "4h", current,
        provider.get_klines_at("BTC/USDT", "4h", rows[4].slot_ts, 5),
        provider.get_klines_at("BTC/USDT", "4h", rows[14].slot_ts, 15),
    )
    assert direct.observation == from_provider.observation
    assert direct.reason == from_provider.reason


def test_provider_keeps_decimal_and_closed_flags():
    provider = HistoricalDataProvider()
    rows = [Kline("1d", NOW, Decimal("12.50"), False)]
    provider.preload("BTC/USDT", "1d", rows)
    row = provider.get_kline_at("BTC/USDT", "1d", NOW)
    assert row.volume_quote == Decimal("12.50")
    assert row.is_closed is False
