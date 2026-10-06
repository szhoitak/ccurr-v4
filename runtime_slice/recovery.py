from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InMemoryRecoverySnapshot:
    pending_orders: dict[str, dict[str, Any]]
    pending_ocos: dict[str, dict[str, Any]]
    unknown_orders: dict[str, dict[str, Any]]
    retry_count: dict[str, int]


@dataclass
class InMemoryOrderRecovery:
    unknown_orders: dict[str, dict[str, Any]] = field(default_factory=dict)
    query_count: dict[str, int] = field(default_factory=dict)
    retry_ids: list[str] = field(default_factory=list)

    def add_unknown(self, client_order_id: str) -> None:
        self.unknown_orders[client_order_id] = {"status": "UNKNOWN"}

    def query(self, client_order_id: str, exchange_status: str) -> str:
        self.query_count[client_order_id] = self.query_count.get(client_order_id, 0) + 1
        self.unknown_orders[client_order_id] = {"status": exchange_status}
        return exchange_status

    def retry_if_not_executed(self, client_order_id: str) -> bool:
        status = self.unknown_orders.get(client_order_id, {}).get("status")
        if status != "NOT_EXECUTED":
            return False
        self.retry_ids.append(client_order_id)
        return True
    def snapshot(self) -> InMemoryRecoverySnapshot:
        return InMemoryRecoverySnapshot(
            pending_orders={},
            pending_ocos={},
            unknown_orders={key: dict(value) for key, value in self.unknown_orders.items()},
            retry_count={},
        )

    def restore(self, snapshot: InMemoryRecoverySnapshot) -> None:
        self.unknown_orders = {key: dict(value) for key, value in snapshot.unknown_orders.items()}
        self.query_count = {key: 0 for key in self.unknown_orders}
        self.retry_ids = []


@dataclass
class PendingOcoRecovery:
    pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    retry_count: dict[str, int] = field(default_factory=dict)

    def register(self, entry_id: str, plan: dict[str, Any]) -> None:
        self.pending[entry_id] = dict(plan)
        self.retry_count.setdefault(entry_id, 0)

    def attempt(self, entry_id: str, placement_succeeded: bool) -> bool:
        if entry_id not in self.pending:
            return False
        if not placement_succeeded:
            self.retry_count[entry_id] += 1
            return False
        self.pending.pop(entry_id)
        return True
    def snapshot(self) -> InMemoryRecoverySnapshot:
        return InMemoryRecoverySnapshot(
            pending_orders={},
            pending_ocos={key: dict(value) for key, value in self.pending.items()},
            unknown_orders={},
            retry_count=dict(self.retry_count),
        )

    def restore(self, snapshot: InMemoryRecoverySnapshot) -> None:
        self.pending = {key: dict(value) for key, value in snapshot.pending_ocos.items()}
        self.retry_count = dict(snapshot.retry_count)


@dataclass
class ReadinessState:
    infrastructure_ready: bool = False
    account_synced: bool = False
    order_recovery_complete: bool = False
    unknown_orders_resolved: bool = False
    pending_oco_recovery_complete: bool = False

    @property
    def can_open(self) -> bool:
        return all(
            (
                self.infrastructure_ready,
                self.account_synced,
                self.order_recovery_complete,
                self.unknown_orders_resolved,
                self.pending_oco_recovery_complete,
            )
        )
