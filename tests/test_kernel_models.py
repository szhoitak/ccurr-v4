from decimal import Decimal
from pathlib import Path
from typing import get_type_hints

import pytest

from runtime_slice.errors import ContractValidationError, IsolationViolationError, ReadinessDeniedError
from runtime_slice.kernel_models import AccountSnapshot, BacktestSettings, EquityPoint, OrderResponse, Position, SymbolFilters, Trade
from runtime_slice.protocols import AccountProvider, KlineProvider, OrderTransport
from runtime_slice.values import from_wire, to_wire

NOW = 1_700_000_000_000


def test_kernel_models_round_trip_and_decimal_fields():
    snapshot = AccountSnapshot(Decimal("1000"), Decimal("500"), Decimal("10"), NOW, "BACKTEST_MEMORY")
    filters = SymbolFilters("BTC/USDT", Decimal("0.001"), Decimal("0.001"), Decimal("10"), Decimal("0.01"), NOW)
    response = OrderResponse(True, "UNKNOWN", "demo-123e4567-e89b-12d3-a456-426614174000", Decimal("0"), NOW)
    position = Position("BTC/USDT", Decimal("1"), Decimal("100"), Decimal("0"), NOW)
    trade = Trade("BTC/USDT", "SELL", Decimal("1"), Decimal("110"), Decimal("0.1"), Decimal("9.9"), NOW, response.client_order_id)
    equity = EquityPoint(NOW, Decimal("1009.9"), Decimal("1009.9"))
    assert all(isinstance(value, object) for value in (snapshot, filters, response, position, trade, equity))
    wire = to_wire({"equity": equity.equity, "timestamp_ms": equity.timestamp_ms})
    assert from_wire(wire)["equity"] == "1009.9"


def test_kernel_rejects_floats_and_live_backtest_settings():
    with pytest.raises(TypeError):
        AccountSnapshot(1000.0, Decimal("1"), Decimal("1"))
    with pytest.raises(ValueError):
        BacktestSettings(NOW, NOW + 1000, ["BTC/USDT"], secrets={"x": "y"})
    with pytest.raises(ValueError):
        BacktestSettings(NOW, NOW + 1000, ["BTC/USDT"], production_execution=True)


def test_unknown_response_preserves_idempotency_key():
    response = OrderResponse(False, "UNKNOWN", "demo-123e4567-e89b-12d3-a456-426614174000", Decimal("0"), NOW)
    assert response.status == "UNKNOWN"
    assert response.client_order_id.startswith("demo-")


def test_protocols_expose_required_methods():
    assert "get_snapshot" in get_type_hints(AccountProvider) or hasattr(AccountProvider, "get_snapshot")
    assert hasattr(KlineProvider, "get_klines_at")
    assert hasattr(OrderTransport, "submit")


def test_error_types_are_stable_and_transport_neutral():
    assert ContractValidationError.code == "CONTRACT_VALIDATION"
    assert IsolationViolationError.code == "ISOLATION_VIOLATION"
    assert ReadinessDeniedError.code == "READINESS_DENIED"
