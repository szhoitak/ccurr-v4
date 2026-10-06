from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .values import decimal_value, validate_epoch_ms


@dataclass
class AccountSnapshot:
    total_account_value: Decimal
    free_usdt: Decimal
    strategy_allocation_pct: Decimal
    captured_at_ms: int | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        self.total_account_value = decimal_value(self.total_account_value)
        self.free_usdt = decimal_value(self.free_usdt)
        self.strategy_allocation_pct = decimal_value(self.strategy_allocation_pct)
        if self.captured_at_ms is not None:
            validate_epoch_ms(self.captured_at_ms)


@dataclass
class SymbolFilters:
    symbol: str
    min_qty: Decimal
    step_size: Decimal
    min_notional: Decimal
    tick_size: Decimal
    captured_at_ms: int | None = None

    def __post_init__(self) -> None:
        for name in ("min_qty", "step_size", "min_notional", "tick_size"):
            setattr(self, name, decimal_value(getattr(self, name)))
        if self.captured_at_ms is not None:
            validate_epoch_ms(self.captured_at_ms)


@dataclass
class BacktestSettings:
    start_ts: int
    end_ts: int
    symbols: list[str]
    timeframes: list[str] = field(default_factory=lambda: ["1d", "4h", "1h"])
    step_ms: int = 300_000
    initial_balance: Decimal = Decimal("10000")
    output_dir: str = "/app/results"
    force_auto: bool = True
    live_dependencies: bool = False
    secrets: dict[str, Any] = field(default_factory=dict)
    production_execution: bool = False

    def __post_init__(self) -> None:
        validate_epoch_ms(self.start_ts)
        validate_epoch_ms(self.end_ts)
        self.initial_balance = decimal_value(self.initial_balance)
        if self.step_ms <= 0:
            raise ValueError("step_ms must be positive")
        if self.live_dependencies or self.secrets or self.production_execution:
            raise ValueError("BacktestSettings cannot enable live dependencies, secrets, or production execution")


@dataclass
class OrderResponse:
    ok: bool
    status: str
    client_order_id: str
    executed_qty: Decimal
    received_at_ms: int
    exchange_order_id: str | None = None
    order_list_id: str | None = None
    avg_price: Decimal | None = None
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        self.executed_qty = decimal_value(self.executed_qty)
        validate_epoch_ms(self.received_at_ms)
        if self.avg_price is not None:
            self.avg_price = decimal_value(self.avg_price)
        if self.status == "UNKNOWN" and not self.client_order_id:
            raise ValueError("UNKNOWN response requires client_order_id")


@dataclass
class Position:
    symbol: str
    quantity: Decimal
    entry_price: Decimal
    realized_pnl: Decimal | None = None
    updated_at_ms: int | None = None

    def __post_init__(self) -> None:
        self.quantity = decimal_value(self.quantity)
        self.entry_price = decimal_value(self.entry_price)
        if self.realized_pnl is not None:
            self.realized_pnl = decimal_value(self.realized_pnl)
        if self.updated_at_ms is not None:
            validate_epoch_ms(self.updated_at_ms)


@dataclass
class Trade:
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    pnl: Decimal | None
    timestamp_ms: int
    client_order_id: str
    entry_order_id: str | None = None
    exit_type: str | None = None

    def __post_init__(self) -> None:
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("trade side must be BUY or SELL")
        self.quantity = decimal_value(self.quantity)
        self.price = decimal_value(self.price)
        self.fee = decimal_value(self.fee)
        if self.pnl is not None:
            self.pnl = decimal_value(self.pnl)
        validate_epoch_ms(self.timestamp_ms)


@dataclass
class EquityPoint:
    timestamp_ms: int
    equity: Decimal
    cash: Decimal | None = None
    unrealized_pnl: Decimal | None = None

    def __post_init__(self) -> None:
        validate_epoch_ms(self.timestamp_ms)
        self.equity = decimal_value(self.equity)
        if self.cash is not None:
            self.cash = decimal_value(self.cash)
        if self.unrealized_pnl is not None:
            self.unrealized_pnl = decimal_value(self.unrealized_pnl)
