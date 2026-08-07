"""_poll() reconnect behavior, with a fully controllable fake backend.

No labgrid ClientSession auto-reconnects on its own after a connection
drops (see exporter._poll's docstring), so this is the exporter's own
retry logic -- worth testing directly, unlike run()'s outer infinite loop,
which stays untested the same way it always has.
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from labgrid_prometheus_exporter_core.exporter import _poll
from labgrid_prometheus_exporter_core.interface import Place, Reservation, Resource
from labgrid_prometheus_exporter_core.metrics import COORDINATOR_CONNECTED, PLACE_ACQUIRED


def _place(*, name: str, acquired: str | None) -> Place:
    return Place(
        name=name,
        aliases=frozenset(),
        comment="",
        acquired=acquired,
        acquired_resources=[],
        changed=1234.5,
        tags={},
    )


class _FakeBackend:
    def __init__(self, *, places: dict[str, Place], connected: bool = True) -> None:
        self._places = places
        self._connected = connected
        self.connect_calls = 0
        self.close_calls = 0
        self.fail_next_connect = False

    async def connect(self) -> None:
        self.connect_calls += 1
        if self.fail_next_connect:
            self.fail_next_connect = False
            raise RuntimeError("connect failed")
        self._connected = True

    async def close(self) -> None:
        self.close_calls += 1

    def places(self) -> dict[str, Place]:
        return self._places

    def resources(self) -> list[Resource]:
        return []

    async def reservations(self) -> list[Reservation]:
        return []

    def connected(self) -> bool:
        return self._connected


def test_poll_refreshes_metrics_when_already_connected() -> None:
    backend = _FakeBackend(places={"a": _place(name="a", acquired="host/user")}, connected=True)

    asyncio.run(_poll(backend))

    assert backend.connect_calls == 0
    assert backend.close_calls == 0
    assert PLACE_ACQUIRED.labels(place="a")._value.get() == 1
    assert COORDINATOR_CONNECTED._value.get() == 1


def test_poll_reconnects_when_disconnected(caplog: pytest.LogCaptureFixture) -> None:
    backend = _FakeBackend(places={"b": _place(name="b", acquired=None)}, connected=False)

    with caplog.at_level(logging.WARNING):
        asyncio.run(_poll(backend))

    assert backend.close_calls == 1
    assert backend.connect_calls == 1
    assert COORDINATOR_CONNECTED._value.get() == 1
    # A successful reconnect must log something, not go silent: that
    # ambiguity (recovered vs. stuck) is exactly what made a real transient
    # failure hard to diagnose from an exporter's logs alone.
    assert "reconnected to coordinator" in caplog.text


def test_poll_keeps_stale_place_metrics_when_reconnect_fails() -> None:
    # Establish known state: place "c" is acquired, and that's reflected.
    backend = _FakeBackend(places={"c": _place(name="c", acquired="host/user")}, connected=True)
    asyncio.run(_poll(backend))
    assert PLACE_ACQUIRED.labels(place="c")._value.get() == 1

    # Now simulate a drop with a failed reconnect. places() reporting empty
    # mirrors what a freshly (re)constructed, not-yet-synced session would
    # actually return -- the scenario update_from_places() must not see.
    backend._connected = False
    backend._places = {}
    backend.fail_next_connect = True

    asyncio.run(_poll(backend))

    assert backend.close_calls == 1
    assert backend.connect_calls == 1
    # Stale metric preserved, not wiped by the empty places() during the outage.
    assert PLACE_ACQUIRED.labels(place="c")._value.get() == 1
    assert COORDINATOR_CONNECTED._value.get() == 0
