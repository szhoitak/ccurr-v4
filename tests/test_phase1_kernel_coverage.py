from decimal import Decimal
from typing import Protocol, runtime_checkable

import pytest

from runtime_slice.errors import (
    ContractValidationError, DecimalValidationError, IsolationViolationError,
    OrderIdentityError, ReadinessDeniedError, TimestampValidationError,
    UnknownOrderStateError,
)
from runtime_slice.kernel_models import AccountSnapshot, BacktestSettings, OrderResponse, SymbolFilters
from runtime_slice.protocols import AccountProvider, FilterProvider, OrderTransport, PositionProvider
from runtime_slice.values import from_wire, to_wire

NOW = 1_700_000_000_000
CID = "demo-123e4567-e89b-12d3-a456-426614174000"


def test_wire_round_trip_preserves_alias_keys_and_decimal_strings():
    payload = {"clientOrderId": CID, "executedQty": Decimal("1.250"), "timestamp_ms": NOW}
    decoded = from_wire(to_wire(payload))
    assert decoded["clientOrderId"] == CID
    assert decoded["executedQty"] == "1.250"
    assert decoded["timestamp_ms"] == NOW


def test_order_response_unknown_requires_retry_correlation():
    unknown = OrderResponse(False, "UNKNOWN", CID, Decimal("0"), NOW)
    retry = OrderResponse(False, "UNKNOWN", CID, Decimal("0"), NOW)
    assert unknown.status == retry.status == "UNKNOWN"
    assert unknown.client_order_id == retry.client_order_id
    with pytest.raises(ValueError):
        OrderResponse(False, "UNKNOWN", "", Decimal("0"), NOW)


def test_settings_isolation_defaults_and_aliases():
    settings = BacktestSettings(NOW, NOW + 1000, ["BTC/USDT"])
    assert settings.timeframes == ["1d", "4h", "1h"]
    assert settings.force_auto is True
    assert settings.live_dependencies is False


def test_protocol_fake_shapes_are_local_only():
    class AccountFake:
        async def get_snapshot(self):
            return AccountSnapshot(Decimal("1000"), Decimal("500"), Decimal("10"))

    class FiltersFake:
        async def get_filters(self, symbol):
            return SymbolFilters(symbol, Decimal("0.001"), Decimal("0.001"), Decimal("10"), Decimal("0.01"))

    assert hasattr(AccountFake(), "get_snapshot")
    assert hasattr(FiltersFake(), "get_filters")
    assert hasattr(OrderTransport, "submit")
    assert hasattr(PositionProvider, "get_position")


def test_error_taxonomy_codes_are_unique_and_stable():
    errors = [ContractValidationError, DecimalValidationError, TimestampValidationError,
              OrderIdentityError, UnknownOrderStateError, ReadinessDeniedError,
              IsolationViolationError]
    codes = [error.code for error in errors]
    assert len(codes) == len(set(codes))
    assert all(code.isupper() for code in codes)
