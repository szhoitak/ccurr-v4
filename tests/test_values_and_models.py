from decimal import Decimal

import pytest

from runtime_slice.models import Candidate, OrderIntent, RiskResult, Signal
from runtime_slice.values import dumps_decimal, validate_epoch_ms


NOW = 1_700_000_000_000


def test_decimal_and_epoch_ms_contract():
    assert validate_epoch_ms(NOW) == NOW
    assert '"price":"1.25"' in dumps_decimal({"price": Decimal("1.25")})
    with pytest.raises(TypeError):
        validate_epoch_ms(1.7)
    with pytest.raises(TypeError):
        dumps_decimal({"price": 1.25})


def test_candidate_terminal_set_preserves_documented_canceled_ambiguity():
    candidate = Candidate("BTC/USDT", "demo", "trace-1", NOW, status="CANCELED")
    assert candidate.is_terminal is False
    candidate.status = "CONFIRMED"
    assert candidate.is_terminal is True


def test_spot_order_rejects_reduce_only_and_preserves_decimal():
    payload = {
        "symbol": "BTC/USDT",
        "strategy_id": "demo",
        "trace_id": "trace-1",
        "signal_id": "sig-1",
        "client_order_id": "demo-123e4567-e89b-12d3-a456-426614174000",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": Decimal("0.1"),
    }
    order = OrderIntent.from_mapping(payload)
    assert order.quantity == Decimal("0.1")
    with pytest.raises(ValueError):
        OrderIntent.from_mapping({**payload, "reduceOnly": False})


def test_signal_and_risk_result_use_decimal_fields():
    signal = Signal("sig", "trace", "demo", NOW, "BTC/USDT", Decimal("10.0"))
    result = RiskResult(True, "BNB", actual_risk_pct=Decimal("1.0"))
    assert signal.weight_pct == Decimal("10.0")
    assert result.actual_risk_pct == Decimal("1.0")
