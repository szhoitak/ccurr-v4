from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable


@dataclass(frozen=True)
class TradeRecord:
    pnl: Decimal
    holding_hours: Decimal | None = None


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return_pct: Decimal
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: Decimal
    profit_factor: Decimal | None
    max_drawdown_pct: Decimal
    sharpe_ratio: Decimal | None = None
    avg_holding_hours: Decimal | None = None


class PerformanceAnalyzer:
    def analyze(self, initial_balance: Decimal, equity_curve: Iterable[Decimal], trades: Iterable[TradeRecord]) -> PerformanceMetrics:
        initial = Decimal(str(initial_balance))
        equity = [Decimal(str(value)) for value in equity_curve]
        trade_rows = list(trades)
        final = equity[-1] if equity else initial
        total_return = (final - initial) / initial * Decimal("100") if initial else Decimal("0")
        wins = sum(1 for trade in trade_rows if trade.pnl > 0)
        losses = sum(1 for trade in trade_rows if trade.pnl < 0)
        gross_profit = sum((trade.pnl for trade in trade_rows if trade.pnl > 0), Decimal("0"))
        gross_loss = sum((-trade.pnl for trade in trade_rows if trade.pnl < 0), Decimal("0"))
        profit_factor = gross_profit / gross_loss if gross_loss else None
        peak = initial
        max_drawdown = Decimal("0")
        for value in [initial, *equity]:
            peak = max(peak, value)
            if peak:
                max_drawdown = max(max_drawdown, (peak - value) / peak * Decimal("100"))
        avg_hours = None
        durations = [trade.holding_hours for trade in trade_rows if trade.holding_hours is not None]
        if durations:
            avg_hours = sum(durations, Decimal("0")) / Decimal(len(durations))
        return PerformanceMetrics(
            total_return_pct=total_return,
            trade_count=len(trade_rows),
            win_count=wins,
            loss_count=losses,
            win_rate=Decimal(wins) / Decimal(len(trade_rows)) if trade_rows else Decimal("0"),
            profit_factor=profit_factor,
            max_drawdown_pct=max_drawdown,
            avg_holding_hours=avg_hours,
        )
