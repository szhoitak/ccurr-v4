from decimal import Decimal

from runtime_slice.mock_broker import MarketBar, MockBroker, OcoPlan
from runtime_slice.models import OrderIntent

CID = "demo-123e4567-e89b-12d3-a456-426614174000"


def order(side, quantity="1", price=Decimal("100")):
    return OrderIntent("BTC/USDT", "demo", "trace", "sig", CID, side, "LIMIT", Decimal(quantity), price=price)


def funded_broker():
    broker = MockBroker(initial_balance=Decimal("1000"))
    broker.place_order(order("BUY"), MarketBar(1, Decimal("99"), Decimal("101"), Decimal("100")))
    return broker


def test_take_profit_trigger_closes_position_and_consumes_oco():
    broker = funded_broker()
    broker.register_oco_plan(OcoPlan("entry-1", "BTC/USDT", Decimal("1"), Decimal("110"), Decimal("90"), Decimal("89")))
    trigger = broker.check_oco_orders("BTC/USDT", MarketBar(2, Decimal("100"), Decimal("110"), Decimal("108")))
    assert trigger.kind == "TAKE_PROFIT"
    fill = broker.close_oco(trigger, 2)
    assert fill.price == Decimal("110")
    assert broker.get_positions()["BTC/USDT"].quantity == Decimal("0")
    assert "entry-1" not in broker.oco_plans


def test_stop_loss_trigger_closes_position_at_stop_limit():
    broker = funded_broker()
    broker.register_oco_plan(OcoPlan("entry-2", "BTC/USDT", Decimal("1"), Decimal("110"), Decimal("90"), Decimal("89")))
    trigger = broker.check_oco_orders("BTC/USDT", MarketBar(2, Decimal("90"), Decimal("100"), Decimal("95")))
    assert trigger.kind == "STOP_LOSS"
    fill = broker.close_oco(trigger, 2)
    assert fill.price == Decimal("89")
    assert broker.get_positions()["BTC/USDT"].quantity == Decimal("0")


def test_trigger_equality_and_dual_trigger_are_explicit():
    broker = funded_broker()
    broker.register_oco_plan(OcoPlan("entry-3", "BTC/USDT", Decimal("1"), Decimal("110"), Decimal("90"), Decimal("89")))
    assert broker.check_oco_orders("BTC/USDT", MarketBar(2, Decimal("100"), Decimal("110"), Decimal("105"))).kind == "TAKE_PROFIT"
    broker.register_oco_plan(OcoPlan("entry-4", "BTC/USDT", Decimal("1"), Decimal("110"), Decimal("90"), Decimal("89")))
    dual = broker.check_oco_orders("BTC/USDT", MarketBar(3, Decimal("90"), Decimal("110"), Decimal("100")))
    assert dual.kind == "AMBIGUOUS_DUAL_TRIGGER"
    assert "entry-4" in broker.oco_plans
