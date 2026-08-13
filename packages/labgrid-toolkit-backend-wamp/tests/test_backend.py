"""WampCoordinatorBackend structurally satisfies the core CoordinatorBackend contract."""

from __future__ import annotations

from labgrid_toolkit_backend_wamp.backend import WampCoordinatorBackend
from labgrid_toolkit_core.interface import CoordinatorBackend


def test_backend_satisfies_protocol() -> None:
    assert isinstance(WampCoordinatorBackend("ws://127.0.0.1:20408/ws"), CoordinatorBackend)


def test_backend_not_connected_before_connect() -> None:
    assert WampCoordinatorBackend("ws://127.0.0.1:20408/ws").connected() is False
