from __future__ import annotations

from typing import Any, Protocol

from .kernel_models import (
    AccountSnapshot,
    EquityPoint,
    OrderResponse,
    Position,
    SymbolFilters,
)
from .models import OrderIntent


class KlineProvider(Protocol):
    def get_klines_at(self, symbol: str, timeframe: str, ts: int, limit: int) -> list[Any]: ...


class ConfigProvider(Protocol):
    async def get_config(self, strategy_id: str) -> dict[str, Any]: ...


class PositionProvider(Protocol):
    async def get_position(self, symbol: str) -> Position | None: ...


class AccountProvider(Protocol):
    async def get_snapshot(self) -> AccountSnapshot: ...


class FilterProvider(Protocol):
    async def get_filters(self, symbol: str) -> SymbolFilters: ...


class OrderTransport(Protocol):
    async def submit(self, intent: OrderIntent) -> OrderResponse: ...
    async def query(self, client_order_id: str) -> OrderResponse: ...


class ResultWriter(Protocol):
    def write_result(self, name: str, payload: str) -> Any: ...


class RecoveryStore(Protocol):
    async def restore_positions(self) -> dict[str, Position]: ...
    async def restore_equity(self) -> list[EquityPoint]: ...
