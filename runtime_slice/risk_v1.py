from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any, Protocol

from .models import RiskResult, Signal
from .values import decimal_value


@dataclass(frozen=True)
class AccountSnapshot:
    total_account_value: Decimal
    strategy_allocation_pct: Decimal
    free_usdt: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "total_account_value", decimal_value(self.total_account_value))
        object.__setattr__(self, "strategy_allocation_pct", decimal_value(self.strategy_allocation_pct))
        object.__setattr__(self, "free_usdt", decimal_value(self.free_usdt))


@dataclass(frozen=True)
class SymbolFilters:
    min_qty: Decimal
    step_size: Decimal
    min_notional: Decimal

    def __post_init__(self) -> None:
        for name in ("min_qty", "step_size", "min_notional"):
            object.__setattr__(self, name, decimal_value(getattr(self, name)))


@dataclass(frozen=True)
class FeePolicy:
    rate: Decimal

    @classmethod
    def for_mode(cls, fee_mode: str) -> "FeePolicy":
        if fee_mode == "BNB":
            return cls(Decimal("0.00075"))
        if fee_mode == "NON_BNB":
            return cls(Decimal("0.001"))
        raise ValueError("fee_mode must be BNB or NON_BNB")


class RiskCalculator(Protocol):
    async def check(self, signal: Signal, account: Any, symbol_filters: Any, fee_mode: str) -> RiskResult: ...


class RiskCalculatorV1:
    """Pure local V1 boundary implementing only explicit Blueprint formulas."""

    def __init__(self, max_risk_per_trade_pct: Decimal = Decimal("2.0")) -> None:
        self.max_risk_per_trade_pct = decimal_value(max_risk_per_trade_pct)

    async def check(
        self,
        signal: Signal,
        account: AccountSnapshot,
        symbol_filters: SymbolFilters,
        fee_mode: str,
    ) -> RiskResult:
        fee = FeePolicy.for_mode(fee_mode).rate
        entry = decimal_value(signal.plan["entry_price"])
        stop_limit = decimal_value(signal.plan["stop_limit_price"])
        current_price = decimal_value(signal.plan.get("current_price", entry))
        strategy_fund = account.total_account_value * account.strategy_allocation_pct / Decimal("100")
        trade_amount = strategy_fund * signal.weight_pct / Decimal("100")
        original_qty = trade_amount / current_price
        stop_distance = entry - stop_limit
        if stop_distance <= 0:
            return RiskResult(False, fee_mode, rule_id="R06", rejection_reason="INVALID_STOP_DISTANCE")
        risk_based_qty = (
            account.total_account_value * self.max_risk_per_trade_pct / Decimal("100")
        ) / stop_distance
        qty = min(original_qty, risk_based_qty)

        estimated_round_trip_fee = qty * entry * fee * Decimal("2")
        expected_loss = qty * stop_distance + estimated_round_trip_fee
        actual_risk_pct = expected_loss / account.total_account_value * Decimal("100")
        if actual_risk_pct > self.max_risk_per_trade_pct:
            return RiskResult(False, fee_mode, risk_amount=expected_loss, actual_risk_pct=actual_risk_pct,
                              rule_id="R06", rejection_reason="RISK_REJECTED")

        qty = (qty / symbol_filters.step_size).to_integral_value(rounding=ROUND_DOWN) * symbol_filters.step_size
        notional = qty * entry
        if qty < symbol_filters.min_qty or notional < symbol_filters.min_notional:
            return RiskResult(False, fee_mode, calculated_qty=qty, notional=notional,
                              rule_id="R14", rejection_reason="MIN_NOTIONAL_REJECT")

        required_quote = notional * (Decimal("1") + fee)
        if required_quote > account.free_usdt:
            return RiskResult(False, fee_mode, calculated_qty=qty, notional=notional,
                              rule_id="R13", rejection_reason="INSUFFICIENT_BALANCE")
        return RiskResult(True, fee_mode, calculated_qty=qty, risk_amount=expected_loss,
                          actual_risk_pct=actual_risk_pct, notional=notional)


class LiveRiskAdapter:
    def __init__(self, calculator: RiskCalculator) -> None:
        self._calculator = calculator

    async def check(self, *args: Any, **kwargs: Any) -> RiskResult:
        return await self._calculator.check(*args, **kwargs)


class BacktestRiskAdapter(LiveRiskAdapter):
    pass
