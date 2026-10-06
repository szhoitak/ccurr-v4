import asyncio
from decimal import Decimal

from runtime_slice.models import Signal
from runtime_slice.risk_v1 import AccountSnapshot, BacktestRiskAdapter, LiveRiskAdapter, RiskCalculatorV1, SymbolFilters


NOW = 1_700_000_000_000
FILTERS = SymbolFilters(Decimal("0.001"), Decimal("0.001"), Decimal("10"))
ACCOUNT = AccountSnapshot(Decimal("10000"), Decimal("100"), Decimal("10000"))


def signal(entry="100", stop="99", current="100", weight="10"):
    return Signal("sig", "trace", "demo", NOW, "BTC/USDT", Decimal(weight), plan={
        "entry_price": Decimal(entry),
        "stop_limit_price": Decimal(stop),
        "current_price": Decimal(current),
    })


def check(calculator, value, mode="NON_BNB"):
    return asyncio.run(calculator.check(value, ACCOUNT, FILTERS, mode))


def test_v1_allows_safe_trade_and_preserves_risk_fields():
    result = check(RiskCalculatorV1(), signal())
    assert result.allowed is True
    assert result.calculated_qty is not None
    assert result.rule_id is None
    assert result.risk_version == "V1"


def test_r06_invalid_stop_distance_vetoes():
    result = check(RiskCalculatorV1(), signal(stop="101"))
    assert result.allowed is False
    assert result.rule_id == "R06"
    assert result.rejection_reason == "INVALID_STOP_DISTANCE"


def test_r12_downward_quantization_never_increases_quantity():
    result = check(RiskCalculatorV1(), signal(weight="1"))
    assert result.allowed is True
    assert result.calculated_qty % FILTERS.step_size == 0


def test_r14_min_notional_rejects_without_upward_resize():
    tiny_filters = SymbolFilters(Decimal("1"), Decimal("1"), Decimal("1000"))
    result = asyncio.run(RiskCalculatorV1().check(signal(weight="0.01"), ACCOUNT, tiny_filters, "NON_BNB"))
    assert result.allowed is False
    assert result.rule_id == "R14"
    assert result.rejection_reason == "MIN_NOTIONAL_REJECT"


def test_r13_free_balance_rejects():
    poor = AccountSnapshot(Decimal("10000"), Decimal("100"), Decimal("1"))
    result = asyncio.run(RiskCalculatorV1().check(signal(), poor, FILTERS, "NON_BNB"))
    assert result.allowed is False
    assert result.rule_id == "R13"
    assert result.rejection_reason == "INSUFFICIENT_BALANCE"


def test_bnb_and_non_bnb_are_explicit_fee_modes():
    bnb = check(RiskCalculatorV1(), signal(), "BNB")
    non_bnb = check(RiskCalculatorV1(), signal(), "NON_BNB")
    assert bnb.fee_mode == "BNB"
    assert non_bnb.fee_mode == "NON_BNB"


def test_live_and_backtest_adapters_share_identical_calculator_result():
    calculator = RiskCalculatorV1()
    live = asyncio.run(LiveRiskAdapter(calculator).check(signal(), ACCOUNT, FILTERS, "NON_BNB"))
    backtest = asyncio.run(BacktestRiskAdapter(calculator).check(signal(), ACCOUNT, FILTERS, "NON_BNB"))
    assert live == backtest
