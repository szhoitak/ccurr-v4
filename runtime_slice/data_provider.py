from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .step2 import Kline


@dataclass
class HistoricalDataProvider:
    """Offline in-memory provider; it never opens a database connection."""

    _rows: dict[str, dict[str, list[Kline]]] = field(default_factory=lambda: defaultdict(dict))
    _index: dict[str, dict[str, dict[int, int]]] = field(default_factory=lambda: defaultdict(dict))

    def preload(self, symbol: str, timeframe: str, rows: list[Kline]) -> None:
        ordered = sorted(rows, key=lambda row: row.slot_ts)
        self._rows[symbol][timeframe] = ordered
        self._index[symbol][timeframe] = {
            row.slot_ts: index for index, row in enumerate(ordered)
        }

    def get_klines_at(self, symbol: str, timeframe: str, ts: int, limit: int) -> list[Kline]:
        rows = self._rows.get(symbol, {}).get(timeframe, [])
        eligible = [row for row in rows if row.slot_ts <= ts]
        return eligible[-limit:] if limit > 0 else []

    def get_kline_at(self, symbol: str, timeframe: str, ts: int) -> Kline | None:
        rows = self.get_klines_at(symbol, timeframe, ts, 1)
        return rows[0] if rows else None

    def get_range(self, symbol: str, timeframe: str, start_ts: int, end_ts: int) -> list[Kline]:
        return [
            row for row in self._rows.get(symbol, {}).get(timeframe, [])
            if start_ts <= row.slot_ts <= end_ts
        ]
