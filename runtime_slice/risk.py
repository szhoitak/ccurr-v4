from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .models import RiskResult, Signal


class RiskCalculator(Protocol):
    async def check(
        self,
        signal: Signal,
        account: Any,
        symbol_filters: Any,
        fee_mode: str,
    ) -> RiskResult: ...


@dataclass
class RecordingRiskCalculator:
    """A boundary double; it deliberately does not implement sizing formulas."""

    veto_at: str | None = None

    def __post_init__(self) -> None:
        self.calls: list[str] = []

    async def check(
        self,
        signal: Signal,
        account: Any,
        symbol_filters: Any,
        fee_mode: str,
    ) -> RiskResult:
        for rule in ("R17", "R06", "R12", "R14", "R13"):
            self.calls.append(rule)
            if rule == self.veto_at:
                return RiskResult(
                    allowed=False,
                    fee_mode=fee_mode,
                    rule_id=rule,
                    rejection_reason=f"{rule}_REJECTED",
                )
        return RiskResult(allowed=True, fee_mode=fee_mode)
