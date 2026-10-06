from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN

from .models import OrderIntent
from .values import decimal_value


@dataclass(frozen=True)
class FillPolicy:
    fee_mode: str
    fee_reserve: Decimal

    @classmethod
    def for_mode(cls, fee_mode: str) -> "FillPolicy":
        if fee_mode == "BNB":
            return cls(fee_mode, Decimal("0"))
        if fee_mode == "NON_BNB":
            return cls(fee_mode, Decimal("0.001"))
        raise ValueError("fee_mode must be BNB or NON_BNB")


@dataclass(frozen=True)
class OcoSafetyResult:
    allowed: bool
    safe_quantity: Decimal | None = None
    reason: str | None = None


def retry_identity(original: OrderIntent, retry: OrderIntent) -> bool:
    return original.client_order_id == retry.client_order_id


def _quantize_down(value: Decimal, step_size: Decimal) -> Decimal:
    units = (value / step_size).to_integral_value(rounding=ROUND_DOWN)
    return units * step_size


def safe_oco_quantity(
    executed_qty: Decimal,
    fee_mode: str,
    step_size: Decimal,
    min_qty: Decimal,
    min_notional: Decimal,
    price: Decimal,
) -> OcoSafetyResult:
    executed_qty = decimal_value(executed_qty)
    step_size = decimal_value(step_size)
    min_qty = decimal_value(min_qty)
    min_notional = decimal_value(min_notional)
    price = decimal_value(price)
    if executed_qty <= 0:
        return OcoSafetyResult(False, reason="NO_EXECUTED_QTY")
    policy = FillPolicy.for_mode(fee_mode)
    retained = executed_qty * (Decimal("1") - policy.fee_reserve)
    safe_qty = _quantize_down(retained, step_size)
    if safe_qty < min_qty:
        return OcoSafetyResult(False, safe_qty, "MIN_QTY_REJECT")
    if safe_qty * price < min_notional:
        return OcoSafetyResult(False, safe_qty, "MIN_NOTIONAL_REJECT")
    return OcoSafetyResult(True, safe_qty)


@dataclass
class PendingOcoStateMachine:
    pending: dict[str, dict] = field(default_factory=dict)
    retries: dict[str, int] = field(default_factory=dict)

    def register(self, entry_id: str, plan: dict) -> None:
        self.pending[entry_id] = dict(plan)
        self.retries.setdefault(entry_id, 0)

    def partial_fill(self, entry_id: str, executed_qty: Decimal) -> bool:
        """Partial fill does not consume/activate pending OCO."""
        return entry_id in self.pending and decimal_value(executed_qty) > 0

    def placement_failed(self, entry_id: str) -> None:
        if entry_id in self.pending:
            self.retries[entry_id] += 1

    def placement_succeeded(self, entry_id: str) -> bool:
        if entry_id not in self.pending:
            return False
        self.pending.pop(entry_id)
        return True
