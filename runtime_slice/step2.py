from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .clock import Clock
from .models import SpikeObservation, SpikeResult
from .values import decimal_value, validate_epoch_ms


@dataclass(frozen=True)
class Kline:
    timeframe: str
    slot_ts: int
    volume_quote: Decimal | None
    is_closed: bool

    def __post_init__(self) -> None:
        validate_epoch_ms(self.slot_ts)
        if self.volume_quote is not None:
            object.__setattr__(self, "volume_quote", decimal_value(self.volume_quote))


@dataclass(frozen=True)
class Step2Decision:
    observation: SpikeObservation | None
    reason: str | None = None


class Step2VolumeEvaluator:
    """Small typed, deterministic Step 2 boundary evaluator."""

    def __init__(
        self,
        clock: Clock,
        threshold_ma7: Decimal = Decimal("3.0"),
        threshold_ma20: Decimal = Decimal("2.0"),
        min_samples_7d: int = 5,
        min_samples_20d: int = 15,
    ) -> None:
        self._clock = clock
        self._threshold_ma7 = decimal_value(threshold_ma7)
        self._threshold_ma20 = decimal_value(threshold_ma20)
        self._min_samples_7d = min_samples_7d
        self._min_samples_20d = min_samples_20d

    def evaluate(
        self,
        symbol: str,
        timeframe: str,
        current: Kline,
        history_7d: Iterable[Kline],
        history_20d: Iterable[Kline],
    ) -> Step2Decision:
        if current.timeframe != timeframe:
            return Step2Decision(None, "timeframe_mismatch")
        rows7 = list(history_7d)
        rows20 = list(history_20d)
        if current.timeframe != timeframe:
            return Step2Decision(None, "timeframe_mismatch")
        if current.volume_quote is None:
            return Step2Decision(None, "missing_volume")
        if timeframe in {"4h", "1h"} and not current.is_closed:
            return Step2Decision(None, "open_candle")
        if len({row.slot_ts for row in rows7}) != len(rows7):
            return Step2Decision(None, "duplicate_slot")
        if len({row.slot_ts for row in rows20}) != len(rows20):
            return Step2Decision(None, "duplicate_slot")
        rows = rows7 + rows20 + [current]
        if any(row.timeframe != timeframe for row in rows):
            return Step2Decision(None, "timeframe_mismatch")
        if len(rows7) < self._min_samples_7d or len(rows20) < self._min_samples_20d:
            return Step2Decision(None, "insufficient_samples")

        volumes7 = [row.volume_quote for row in rows7]
        volumes20 = [row.volume_quote for row in rows20]
        if any(value is None for value in volumes7 + volumes20):
            return Step2Decision(None, "missing_volume")
        ma7 = sum(volumes7, Decimal("0")) / Decimal(len(volumes7))
        ma20 = sum(volumes20, Decimal("0")) / Decimal(len(volumes20))
        if ma7 == 0 or ma20 == 0:
            return Step2Decision(None, "zero_denominator")
        rvol7 = current.volume_quote / ma7
        rvol20 = current.volume_quote / ma20
        observation = SpikeObservation(
            timeframe=timeframe,
            slot_ts=current.slot_ts,
            current_volume_quote=current.volume_quote,
            ma7=ma7,
            ma20=ma20,
            rvol_ma7=rvol7,
            rvol_ma20=rvol20,
            is_closed=current.is_closed,
            elapsed_ms=self._clock.now_ms() - current.slot_ts,
            is_spike=rvol7 >= self._threshold_ma7 or rvol20 >= self._threshold_ma20,
        )
        return Step2Decision(observation)

    def scan(self, symbol: str, rows: Iterable[Kline]) -> SpikeResult:
        observations: list[SpikeObservation] = []
        reasons: list[str] = []
        for current in rows:
            decision = self.evaluate(symbol, current.timeframe, current, [], [])
            if decision.observation is not None:
                observations.append(decision.observation)
            elif decision.reason is not None:
                reasons.append(decision.reason)
        return SpikeResult(
            symbol=symbol,
            observations=observations,
            spike_timeframes=[item.timeframe for item in observations if item.is_spike],
            is_conflict=len(set(item.timeframe for item in observations)) > 1,
            skipped_reasons=reasons,
        )
