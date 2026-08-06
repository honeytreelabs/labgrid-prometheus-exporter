"""CoordinatorBackend implementation for labgrid's WAMP coordinator protocol."""

from __future__ import annotations

import asyncio
from typing import Any

from autobahn.asyncio.wamp import ApplicationRunner
from labgrid.remote.client import ClientSession
from labgrid.remote.common import Place as LabgridPlace
from labgrid.util.proxy import proxymanager
from labgrid_prometheus_exporter_core.interface import Place


def _convert(place: LabgridPlace) -> Place:
    return Place(
        name=place.name,
        aliases=frozenset(place.aliases),
        comment=place.comment,
        acquired=place.acquired,
        acquired_resources=[str(resource_path) for resource_path in place.acquired_resources],
        changed=place.changed,
        tags=dict(place.tags),
        reservation=place.reservation,
    )


class WampCoordinatorBackend:
    """Talks to a labgrid < 25.0 coordinator over WAMP/crossbar.

    Wraps labgrid's own ClientSession (an autobahn ApplicationSession)
    instead of reimplementing the protocol, mirroring how
    GrpcCoordinatorBackend wraps the gRPC-era ClientSession. The connection
    setup below follows labgrid.remote.client.start_session() directly,
    adapted from loop.run_until_complete() calls to plain awaits since we
    already run inside our own event loop.
    """

    def __init__(self, url: str, realm: str = "realm1") -> None:
        self._url = url
        self._realm = realm
        self._session: ClientSession | None = None
        # autobahn doesn't expose a clean public type for this (an internal
        # WampWebSocketClientProtocol); Any reflects that honestly.
        self._protocol: Any = None

    async def connect(self) -> None:
        loop = asyncio.get_running_loop()
        ready = asyncio.Event()

        async def connected(session: ClientSession) -> None:
            ready.set()

        extra = {"loop": loop, "connected": connected}
        session_holder: list[ClientSession | None] = [None]

        def make(*args, **kwargs) -> ClientSession:
            session_holder[0] = ClientSession(*args, **kwargs)
            return session_holder[0]

        url = proxymanager.get_url(self._url, default_port=20408)
        runner = ApplicationRunner(url, realm=self._realm, extra=extra)
        _, protocol = await runner.run(make, start_loop=False)

        done, pending = await asyncio.wait(
            {protocol.is_open, protocol.is_closed}, timeout=30, return_when=asyncio.FIRST_COMPLETED
        )
        if protocol.is_closed in done:
            raise RuntimeError("connection closed during setup")
        if protocol.is_open in pending:
            raise RuntimeError("connection timed out during setup")

        await ready.wait()
        self._session = session_holder[0]
        self._protocol = protocol

    async def close(self) -> None:
        if self._session is None:
            return
        self._session.leave()
        await asyncio.wait_for(self._protocol.is_closed, timeout=10)
        self._session = None
        self._protocol = None

    def places(self) -> dict[str, Place]:
        if self._session is None:
            raise RuntimeError("not connected: call connect() first")
        return {name: _convert(place) for name, place in self._session.places.items()}

    def connected(self) -> bool:
        return self._session is not None and self._session.is_connected()
