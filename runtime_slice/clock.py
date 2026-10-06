from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Clock(Protocol):
    def now_ms(self) -> int: ...


@dataclass
class VirtualClock:
    start_ts: int
    end_ts: int
    step_ms: int = 300_000

    def __post_init__(self) -> None:
        if not isinstance(self.start_ts, int) or not isinstance(self.end_ts, int):
            raise TypeError("timestamps must be integers")
        if self.step_ms <= 0:
            raise ValueError("step_ms must be positive")
        self._current = self.start_ts

    def now_ms(self) -> int:
        return self._current

    def advance(self) -> bool:
        self._current += self.step_ms
        return self._current < self.end_ts

    def is_finished(self) -> bool:
        return self._current >= self.end_ts

    def reset(self) -> None:
        self._current = self.start_ts
