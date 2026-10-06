from decimal import Decimal

import pytest

from runtime_slice.models import OrderIntent
from runtime_slice.order_safety import PendingOcoStateMachine, retry_identity, safe_oco_quantity


CID = "demo-123e4567-e89b-12d3-a456-426614174000"


def make_order(client_id=CID):
    return OrderIntent("BTC/USDT", "demo", "trace", "sig", client_id, "BUY", "LIMIT", Decimal("1"))


def test_retry_reuses_client_order_id_and_not_exchange_id():
    original = make_order()
    retry = make_order()
    assert retry_identity(original, retry) is True
    different = make_order("demo-123e4567-e89b-12d3-a456-426614174001")
    assert retry_identity(original, different) is False


def test_non_bnb_partial_fill_reserves_fee_and_quantizes_down():
    result = safe_oco_quantity(Decimal("1.001"), "NON_BNB", Decimal("0.1"), Decimal("0.1"), Decimal("10"), Decimal("100"))
    assert result.allowed is True
    assert result.safe_quantity == Decimal("0.9")
    assert result.safe_quantity < Decimal("1.001")


def test_bnb_does_not_apply_non_bnb_reserve():
    result = safe_oco_quantity(Decimal("1.05"), "BNB", Decimal("0.1"), Decimal("0.1"), Decimal("10"), Decimal("100"))
    assert result.allowed is True
    assert result.safe_quantity == Decimal("1.0")


def test_zero_executed_quantity_is_rejected():
    result = safe_oco_quantity(Decimal("0"), "NON_BNB", Decimal("0.1"), Decimal("0.1"), Decimal("1"), Decimal("100"))
    assert result.allowed is False
    assert result.reason == "NO_EXECUTED_QTY"


def test_min_qty_and_notional_reject_without_upward_resize():
    qty = safe_oco_quantity(Decimal("0.11"), "BNB", Decimal("0.1"), Decimal("0.2"), Decimal("1"), Decimal("100"))
    assert qty.allowed is False
    assert qty.reason == "MIN_QTY_REJECT"
    notional = safe_oco_quantity(Decimal("0.11"), "BNB", Decimal("0.1"), Decimal("0.1"), Decimal("20"), Decimal("100"))
    assert notional.allowed is False
    assert notional.reason == "MIN_NOTIONAL_REJECT"


def test_pending_oco_partial_fill_failure_retention_success_consumption():
    state = PendingOcoStateMachine()
    state.register("entry-1", {"tp": "101", "sl": "99"})
    assert state.partial_fill("entry-1", Decimal("0.5")) is True
    assert "entry-1" in state.pending
    state.placement_failed("entry-1")
    assert state.retries["entry-1"] == 1
    assert "entry-1" in state.pending
    assert state.placement_succeeded("entry-1") is True
    assert "entry-1" not in state.pending
