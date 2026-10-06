from __future__ import annotations

import socket

import pytest


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args, **kwargs):
        raise AssertionError("external network is forbidden in G3 local-only tests")

    monkeypatch.setattr(socket, "create_connection", denied)
