from decimal import Decimal

from runtime_slice.performance import PerformanceAnalyzer, TradeRecord


def test_performance_metrics():
    metrics = PerformanceAnalyzer().analyze(
        Decimal("100"),
        [Decimal("100"), Decimal("110"), Decimal("99"), Decimal("120")],
        [TradeRecord(Decimal("10"), Decimal("2")), TradeRecord(Decimal("-5"), Decimal("4"))],
    )
    assert metrics.total_return_pct == Decimal("20")
    assert metrics.trade_count == 2
    assert metrics.win_count == 1
    assert metrics.loss_count == 1
    assert metrics.win_rate == Decimal("0.5")
    assert metrics.profit_factor == Decimal("2")
    assert metrics.max_drawdown_pct == Decimal("10")
    assert metrics.avg_holding_hours == Decimal("3")


def test_performance_metrics_keep_undefined_sharpe_as_none():
    metrics = PerformanceAnalyzer().analyze(Decimal("100"), [], [])
    assert metrics.sharpe_ratio is None
