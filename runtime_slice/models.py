from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import re
from typing import Any

from .values import decimal_value, validate_epoch_ms


TERMINAL_CANDIDATE_STATUSES = frozenset(
    {
        "CONFIRMED",
        "REJECTED",
        "MANUAL_PRICE_DEVIATION_REJECT",
        "TIMEOUT_AUTO",
        "TIMEOUT_CANCEL",
    }
)


@dataclass
class SpikeObservation:
    timeframe: str
    slot_ts: int
    current_volume_quote: Decimal
    ma7: Decimal | None = None
    ma20: Decimal | None = None
    rvol_ma7: Decimal | None = None
    rvol_ma20: Decimal | None = None
    is_closed: bool = False
    elapsed_ms: int | None = None
    is_spike: bool = False

    def __post_init__(self) -> None:
        validate_epoch_ms(self.slot_ts)
        self.current_volume_quote = decimal_value(self.current_volume_quote)
        for name in ("ma7", "ma20", "rvol_ma7", "rvol_ma20"):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, decimal_value(value))


@dataclass
class SpikeResult:
    symbol: str
    observations: list[SpikeObservation]
    spike_timeframes: list[str]
    is_conflict: bool = False
    skipped_reasons: list[str] = field(default_factory=list)


@dataclass
class Candidate:
    symbol: str
    strategy_id: str
    trace_id: str
    generated_at_ms: int
    status: str = "PENDING_REVIEW"
    review_action: str | None = None
    review_responded_at_ms: int | None = None
    custom_tp: Decimal | None = None
    score: Decimal = Decimal("0.0")
    current_price: Decimal | None = None
    support_type: str | None = None
    support_target_price: Decimal | None = None
    origin_low: Decimal | None = None
    peak_high: Decimal | None = None
    previous_range_high: Decimal | None = None
    drawdown_pct: Decimal | None = None
    profit_potential_pct: Decimal | None = None
    data: dict[str, Any] = field(default_factory=dict)
    review_deadline_ms: int | None = None

    def __post_init__(self) -> None:
        validate_epoch_ms(self.generated_at_ms)
        if self.review_responded_at_ms is not None:
            validate_epoch_ms(self.review_responded_at_ms)
        if self.review_deadline_ms is not None:
            validate_epoch_ms(self.review_deadline_ms)
        self.score = decimal_value(self.score)
        for name in (
            "custom_tp", "current_price", "support_target_price", "origin_low",
            "peak_high", "previous_range_high", "drawdown_pct",
            "profit_potential_pct",
        ):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, decimal_value(value))

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_CANDIDATE_STATUSES


@dataclass
class Signal:
    signalId: str
    traceId: str
    strategyId: str
    timestamp_ms: int
    symbol: str
    weight_pct: Decimal
    action: str = "OPEN_LONG"
    plan: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_epoch_ms(self.timestamp_ms)
        self.weight_pct = decimal_value(self.weight_pct)


_CLIENT_ORDER_ID = re.compile(r"^[A-Za-z0-9_.-]+-[0-9a-fA-F-]{32,36}$")


@dataclass
class OrderIntent:
    symbol: str
    strategy_id: str
    trace_id: str
    signal_id: str
    client_order_id: str
    side: str
    order_type: str
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: str = "GTC"

    def __post_init__(self) -> None:
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("Spot order side must be BUY or SELL")
        if self.order_type not in {"LIMIT", "MARKET"}:
            raise ValueError("unsupported Spot order type")
        if not _CLIENT_ORDER_ID.fullmatch(self.client_order_id):
            raise ValueError("client_order_id must use strategy_id-uuid4 shape")
        self.quantity = decimal_value(self.quantity)
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.price is not None:
            self.price = decimal_value(self.price)
        if self.stop_price is not None:
            self.stop_price = decimal_value(self.stop_price)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "OrderIntent":
        if "reduceOnly" in payload or "reduce_only" in payload:
            raise ValueError("reduceOnly is forbidden for Spot orders")
        return cls(**payload)


@dataclass
class OtoOrderIntent:
    list_client_order_id: str
    entry: OrderIntent
    pending_quantity: Decimal
    take_profit: OrderIntent | None = None
    stop_loss: OrderIntent | None = None

    def __post_init__(self) -> None:
        self.pending_quantity = decimal_value(self.pending_quantity)
        if self.pending_quantity <= 0:
            raise ValueError("pending_quantity must be positive")


@dataclass
class OrderIdentity:
    trace_id: str
    signal_id: str
    client_order_id: str
    exchange_order_id: str | None = None
    order_list_id: str | None = None


@dataclass
class RiskResult:
    allowed: bool
    fee_mode: str
    calculated_qty: Decimal | None = None
    risk_amount: Decimal | None = None
    actual_risk_pct: Decimal | None = None
    notional: Decimal | None = None
    rejection_reason: str | None = None
    rule_id: str | None = None
    risk_version: str = "V1"

    def __post_init__(self) -> None:
        if self.fee_mode not in {"BNB", "NON_BNB"}:
            raise ValueError("fee_mode must be BNB or NON_BNB")
        for name in ("calculated_qty", "risk_amount", "actual_risk_pct", "notional"):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, decimal_value(value))
