import asyncio
from decimal import Decimal

from runtime_slice.models import Signal
from runtime_slice.risk import RecordingRiskCalculator


NOW = 1_700_000_000_000
SIGNAL = Signal("sig", "trace", "demo", NOW, "BTC/USDT", Decimal("10.0"))


def test_risk_order_and_success_boundary():
    calculator = RecordingRiskCalculator()
    result = asyncio.run(calculator.check(SIGNAL, object(), object(), "BNB"))
    assert calculator.calls == ["R17", "R06", "R12", "R14", "R13"]
    assert result.allowed is True


def test_r06_veto_stops_later_rules():
    calculator = RecordingRiskCalculator(veto_at="R06")
    result = asyncio.run(calculator.check(SIGNAL, object(), object(), "NON_BNB"))
    assert calculator.calls == ["R17", "R06"]
    assert result.allowed is False
    assert result.rule_id == "R06"
