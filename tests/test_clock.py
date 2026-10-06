from runtime_slice.clock import VirtualClock


def test_virtual_clock_boundary_and_reset():
    clock = VirtualClock(1_700_000_000_000, 1_700_000_000_600, 300)
    assert clock.now_ms() == 1_700_000_000_000
    assert clock.advance() is True
    assert clock.now_ms() == 1_700_000_000_300
    assert clock.advance() is False
    assert clock.is_finished() is True
    clock.reset()
    assert clock.now_ms() == clock.start_ts
