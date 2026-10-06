from decimal import Decimal

from runtime_slice.mock_broker import MarketBar, MockBroker
from runtime_slice.models import OrderIntent


CID = "demo-123e4567-e89b-12d3-a456-426614174000"


def order(side, order_type, quantity="1", price=None):
    return OrderIntent("BTC/USDT", "demo", "trace", "sig", CID, side, order_type, Decimal(quantity), price=price)


def test_limit_buy_and_sell_fill_boundaries_and_fee():
    broker = MockBroker(fee_pct=Decimal("0.1"), initial_balance=Decimal("1000"))
    buy = broker.place_order(order("BUY", "LIMIT", price=Decimal("100")), MarketBar(1, Decimal("99"), Decimal("101"), Decimal("100")))
    assert buy is not None
    assert buy.price == Decimal("100")
    assert buy.fee == Decimal("0.1")
    assert broker.get_positions()["BTC/USDT"].quantity == Decimal("1")
    sell = broker.place_order(order("SELL", "LIMIT", price=Decimal("101")), MarketBar(2, Decimal("100"), Decimal("101"), Decimal("101")))
    assert sell is not None
    assert broker.get_positions()["BTC/USDT"].quantity == Decimal("0")


def test_unfilled_limit_has_no_side_effect():
    broker = MockBroker()
    result = broker.place_order(order("BUY", "LIMIT", price=Decimal("90")), MarketBar(1, Decimal("99"), Decimal("101"), Decimal("100")))
    assert result is None
    assert broker.get_trades() == []


def test_market_slippage_and_equity_curve_are_decimal():
    broker = MockBroker(slippage_pct=Decimal("0.05"), initial_balance=Decimal("1000"))
    fill = broker.place_order(order("BUY", "MARKET"), MarketBar(1, Decimal("99"), Decimal("101"), Decimal("100")))
    assert fill is not None
    assert fill.price == Decimal("100.050")
    equity = broker.record_equity({"BTC/USDT": Decimal("101")})
    assert isinstance(equity, Decimal)
    assert broker.equity_curve == [equity]
