from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .models import OrderIntent


@dataclass(frozen=True)
class MarketBar:
    timestamp: int
    low: Decimal
    high: Decimal
    close: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "low", Decimal(str(self.low)))
        object.__setattr__(self, "high", Decimal(str(self.high)))
        object.__setattr__(self, "close", Decimal(str(self.close)))


@dataclass(frozen=True)
class FillRecord:
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    timestamp: int


@dataclass
class Position:
    symbol: str
    quantity: Decimal = Decimal("0")
    entry_price: Decimal = Decimal("0")


@dataclass(frozen=True)
class OcoPlan:
    entry_id: str
    symbol: str
    quantity: Decimal
    take_profit_price: Decimal
    stop_price: Decimal
    stop_limit_price: Decimal


@dataclass(frozen=True)
class OcoTrigger:
    entry_id: str
    kind: str
    price: Decimal
    quantity: Decimal


@dataclass
class MockBroker:
    fee_pct: Decimal = Decimal("0.1")
    slippage_pct: Decimal = Decimal("0.05")
    initial_balance: Decimal = Decimal("10000")
    pending_ocos: dict[str, dict[str, Any]] = field(default_factory=dict)
    oco_plans: dict[str, OcoPlan] = field(default_factory=dict)
    trades: list[FillRecord] = field(default_factory=list)
    positions: dict[str, Position] = field(default_factory=dict)
    equity_curve: list[Decimal] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.fee_rate = Decimal(str(self.fee_pct)) / Decimal("100")
        self.slippage_rate = Decimal(str(self.slippage_pct)) / Decimal("100")
        self._balance = Decimal(str(self.initial_balance))

    def register_pending_oco(self, client_order_id: str, plan: dict[str, Any]) -> None:
        self.pending_ocos[client_order_id] = dict(plan)

    def has_pending_oco(self, client_order_id: str) -> bool:
        return client_order_id in self.pending_ocos

    def pop_pending_oco(self, client_order_id: str) -> dict[str, Any] | None:
        return self.pending_ocos.pop(client_order_id, None)

    def register_oco_plan(self, plan: OcoPlan) -> None:
        self.oco_plans[plan.entry_id] = plan

    def check_oco_orders(self, symbol: str, bar: MarketBar) -> OcoTrigger | None:
        for entry_id, plan in self.oco_plans.items():
            if plan.symbol != symbol:
                continue
            tp_hit = bar.high >= plan.take_profit_price
            sl_hit = bar.low <= plan.stop_price
            if tp_hit and sl_hit:
                return OcoTrigger(entry_id, "AMBIGUOUS_DUAL_TRIGGER", bar.close, plan.quantity)
            if tp_hit:
                return OcoTrigger(entry_id, "TAKE_PROFIT", plan.take_profit_price, plan.quantity)
            if sl_hit:
                return OcoTrigger(entry_id, "STOP_LOSS", plan.stop_limit_price, plan.quantity)
        return None

    def close_oco(self, trigger: OcoTrigger, timestamp: int) -> FillRecord | None:
        if trigger.kind == "AMBIGUOUS_DUAL_TRIGGER":
            return None
        plan = self.oco_plans.get(trigger.entry_id)
        if plan is None:
            return None
        order = OrderIntent(plan.symbol, "demo", "trace", "oco", "demo-123e4567-e89b-12d3-a456-426614174000", "SELL", "LIMIT", trigger.quantity, price=trigger.price)
        fill = self.place_order(order, MarketBar(timestamp, trigger.price, trigger.price, trigger.price))
        if fill is not None:
            self.oco_plans.pop(trigger.entry_id, None)
            self.pending_ocos.pop(trigger.entry_id, None)
        return fill

    def place_order(self, order: OrderIntent, bar: MarketBar) -> FillRecord | None:
        if order.order_type == "MARKET":
            price = bar.close * (Decimal("1") + self.slippage_rate if order.side == "BUY" else Decimal("1") - self.slippage_rate)
        elif order.order_type == "LIMIT":
            if order.price is None:
                raise ValueError("LIMIT order requires price")
            if order.side == "BUY" and bar.low > order.price:
                return None
            if order.side == "SELL" and bar.high < order.price:
                return None
            price = order.price
        else:
            raise ValueError("unsupported order type")
        fee = price * order.quantity * self.fee_rate
        if order.side == "BUY":
            self._balance -= price * order.quantity + fee
            position = self.positions.setdefault(order.symbol, Position(order.symbol))
            position.entry_price = ((position.entry_price * position.quantity) + (price * order.quantity)) / (position.quantity + order.quantity) if position.quantity else price
            position.quantity += order.quantity
        else:
            self._balance += price * order.quantity - fee
            position = self.positions.setdefault(order.symbol, Position(order.symbol))
            position.quantity -= order.quantity
        fill = FillRecord(order.symbol, order.side, order.quantity, price, fee, bar.timestamp)
        self.trades.append(fill)
        return fill

    def get_balance(self) -> Decimal:
        return self._balance

    def get_positions(self) -> dict[str, Position]:
        return self.positions

    def get_trades(self) -> list[FillRecord]:
        return list(self.trades)

    def get_equity(self, prices: dict[str, Decimal]) -> Decimal:
        equity = self._balance
        for symbol, position in self.positions.items():
            equity += position.quantity * Decimal(str(prices.get(symbol, position.entry_price)))
        return equity

    def record_equity(self, prices: dict[str, Decimal]) -> Decimal:
        equity = self.get_equity(prices)
        self.equity_curve.append(equity)
        return equity
