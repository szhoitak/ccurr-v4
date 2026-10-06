from runtime_slice.mock_broker import MockBroker


def test_pending_oco_public_boundary():
    broker = MockBroker()
    broker.register_pending_oco("entry-1", {"take_profit": "1.1"})
    assert broker.has_pending_oco("entry-1") is True
    assert broker.has_pending_oco("missing") is False
    assert broker.pop_pending_oco("entry-1") == {"take_profit": "1.1"}
    assert broker.has_pending_oco("entry-1") is False
    assert broker.pop_pending_oco("entry-1") is None


def test_failed_placement_does_not_consume_pending_oco():
    broker = MockBroker()
    broker.register_pending_oco("entry-2", {"stop_loss": "0.9"})
    # A failed adapter call does not call pop; retry state remains available.
    assert broker.has_pending_oco("entry-2") is True
