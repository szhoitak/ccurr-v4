from __future__ import annotations

import json
from decimal import Decimal
from typing import Any


_MIN_EPOCH_MS = 100_000_000_000
_MAX_EPOCH_MS = 9_999_999_999_999


def validate_epoch_ms(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("epoch milliseconds must be an integer")
    if not _MIN_EPOCH_MS <= value <= _MAX_EPOCH_MS:
        raise ValueError("epoch milliseconds must be a 13-digit UTC value")
    return value


def decimal_value(value: Decimal | str | int) -> Decimal:
    if isinstance(value, float):
        raise TypeError("binary floats are not accepted for canonical numeric fields")
    if not isinstance(value, (Decimal, str, int)):
        raise TypeError("value must be Decimal, string, or integer")
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Decimal must be finite")
    return result


def decimal_json(value: Decimal) -> str:
    return format(decimal_value(value), "f")


def dumps_decimal(payload: Any) -> str:
    def encode(value: Any) -> Any:
        if isinstance(value, float):
            raise TypeError("binary floats are not accepted for canonical numeric fields")
        if isinstance(value, Decimal):
            return decimal_json(value)
        if isinstance(value, dict):
            return {key: encode(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [encode(item) for item in value]
        return value

    return json.dumps(encode(payload), sort_keys=True, separators=(",", ":"))


def to_wire(payload: Any) -> str:
    return dumps_decimal(payload)


def from_wire(payload: str) -> Any:
    return json.loads(payload, parse_float=Decimal)
