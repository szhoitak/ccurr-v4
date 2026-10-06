from runtime_slice.recovery import InMemoryOrderRecovery, PendingOcoRecovery, ReadinessState


def test_unknown_order_is_queried_before_retry():
    recovery = InMemoryOrderRecovery()
    recovery.add_unknown("order-1")
    assert recovery.retry_if_not_executed("order-1") is False
    assert recovery.query("order-1", "UNKNOWN") == "UNKNOWN"
    assert recovery.retry_if_not_executed("order-1") is False
    assert recovery.query("order-1", "NOT_EXECUTED") == "NOT_EXECUTED"
    assert recovery.retry_if_not_executed("order-1") is True
    assert recovery.query_count["order-1"] == 2


def test_pending_oco_failure_retains_state_and_success_consumes_it():
    recovery = PendingOcoRecovery()
    recovery.register("entry-1", {"tp": "1.1"})
    assert recovery.attempt("entry-1", False) is False
    assert recovery.pending["entry-1"] == {"tp": "1.1"}
    assert recovery.retry_count["entry-1"] == 1
    assert recovery.attempt("entry-1", True) is True
    assert "entry-1" not in recovery.pending


def test_readiness_denies_open_until_every_gate_is_complete():
    state = ReadinessState()
    assert state.can_open is False
    state.infrastructure_ready = True
    state.account_synced = True
    state.order_recovery_complete = True
    state.unknown_orders_resolved = True
    assert state.can_open is False
    state.pending_oco_recovery_complete = True
    assert state.can_open is True
