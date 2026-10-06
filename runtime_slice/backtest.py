from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from .clock import VirtualClock
from .isolation import BacktestBoundary
from .mock_broker import MockBroker
from .registry import PluginRegistry
from .performance import PerformanceAnalyzer, PerformanceMetrics, TradeRecord


@dataclass
class BacktestResult:
    strategy_id: str
    start_ts: int
    end_ts: int
    initial_balance: Decimal
    final_balance: Decimal
    trade_count: int = 0
    equity_curve: list[Decimal] = field(default_factory=list)
    output_path: Path | None = None
    metrics: PerformanceMetrics | None = None


class ParameterSweep:
    """Offline sweep boundary; one failed combination does not abort others."""

    async def run(self, combinations: list[dict[str, Any]], callback: Any) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for combination in combinations:
            try:
                results.append({"config": combination, "result": await callback(combination), "error": None})
            except Exception as exc:
                results.append({"config": combination, "result": None, "error": str(exc)})
        return results


class BacktestEngine:
    """Minimal offline orchestration boundary; not a production engine."""

    def __init__(self, registry: PluginRegistry, result_boundary: BacktestBoundary) -> None:
        self.registry = registry
        self.result_boundary = result_boundary

    async def run(
        self,
        strategy_id: str,
        config: dict[str, Any],
        start_ts: int,
        end_ts: int,
        context_builder: Any,
        initial_balance: Decimal = Decimal("10000"),
        step_ms: int = 300_000,
    ) -> BacktestResult:
        strategy_cls = self.registry.get(strategy_id)
        strategy = strategy_cls(config, context_builder)
        await strategy.run_once()
        clock = context_builder.clock
        while not clock.is_finished():
            clock.advance()
        result = BacktestResult(
            strategy_id=strategy_id,
            start_ts=start_ts,
            end_ts=end_ts,
            initial_balance=initial_balance,
            final_balance=initial_balance,
            metrics=PerformanceAnalyzer().analyze(initial_balance, [initial_balance], []),
        )
        result.output_path = self.result_boundary.write_result(
            f"{strategy_id}-{start_ts}-{end_ts}.json",
            "{\"status\":\"offline-boundary-only\"}",
        )
        return result
