import pytest

from runtime_slice.isolation import BacktestBoundary, IsolationGuard
from runtime_slice.recovery import InMemoryOrderRecovery, PendingOcoRecovery, ReadinessState


def test_backtest_boundary_only_writes_inside_isolated_root(tmp_path):
    boundary = BacktestBoundary(tmp_path)
    result = boundary.write_result("run.json", "{}")
    assert result.read_text() == "{}"
    with pytest.raises(ValueError):
        boundary.write_result("../escape.json", "bad")


def test_backtest_boundary_rejects_live_dependencies_and_secrets(tmp_path):
    with pytest.raises(ValueError):
        BacktestBoundary(tmp_path, live_dependencies_enabled=True)
    with pytest.raises(ValueError):
        BacktestBoundary(tmp_path, secrets_available=True)
    with pytest.raises(AssertionError):
        IsolationGuard.assert_no_production_mode("live", {})
    with pytest.raises(AssertionError):
        IsolationGuard.assert_no_production_mode("backtest", {"BINANCE_KEY": "x"})


def test_recovery_source_guard_rejects_external_imports():
    with pytest.raises(AssertionError):
        IsolationGuard.assert_source_safe("import redis")
    IsolationGuard.assert_source_safe("from decimal import Decimal")


def test_unknown_order_snapshot_restore_still_requires_query():
    original = InMemoryOrderRecovery()
    original.add_unknown("order-1")
    snapshot = original.snapshot()
    restored = InMemoryOrderRecovery()
    restored.restore(snapshot)
    assert restored.retry_if_not_executed("order-1") is False
    assert restored.query("order-1", "NOT_EXECUTED") == "NOT_EXECUTED"
    assert restored.retry_if_not_executed("order-1") is True


def test_pending_oco_snapshot_restore_preserves_retry_state():
    original = PendingOcoRecovery()
    original.register("entry-1", {"tp": "101"})
    original.attempt("entry-1", False)
    snapshot = original.snapshot()
    restored = PendingOcoRecovery()
    restored.restore(snapshot)
    assert restored.pending["entry-1"] == {"tp": "101"}
    assert restored.retry_count["entry-1"] == 1
    assert restored.attempt("entry-1", True) is True


def test_readiness_denies_before_recovery_and_allows_after():
    state = ReadinessState(True, True, False, False, False)
    assert state.can_open is False
    state.order_recovery_complete = True
    state.unknown_orders_resolved = True
    state.pending_oco_recovery_complete = True
    assert state.can_open is True
