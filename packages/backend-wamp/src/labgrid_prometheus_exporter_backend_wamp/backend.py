"""CoordinatorBackend implementation for labgrid's WAMP coordinator protocol."""

from __future__ import annotations

import asyncio
from typing import Any

import txaio
from autobahn.asyncio.wamp import ApplicationRunner
from labgrid.remote.client import ClientSession
from labgrid.remote.common import Place as LabgridPlace
from labgrid.remote.common import Reservation as LabgridReservation
from labgrid.remote.common import ReservationState, ResourceEntry
from labgrid.util import filter_dict
from labgrid.util.proxy import proxymanager
from labgrid_prometheus_exporter_core.interface import Place, Reservation, Resource


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


def _convert_resource(
    labgrid_exporter: str, group: str, name: str, entry: ResourceEntry
) -> Resource:
    return Resource(
        labgrid_exporter=labgrid_exporter, group=group, name=name, cls=entry.cls, avail=entry.avail
    )


def _convert_reservation(res: LabgridReservation) -> Reservation:
    return Reservation(
        owner=res.owner, created=res.created, pending=res.state == ReservationState.waiting
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
        # labgrid.remote.client sets txaio.config.loop = asyncio.get_event_loop()
        # at *import* time, before our own asyncio.run() has created the loop
        # this coroutine actually runs on -- get_event_loop() at that point
        # creates and returns a throwaway loop that's never driven. Autobahn
        # schedules its internal timers (connection timeouts, WAMP ping/pong
        # keepalive, ...) via txaio.call_later(), which uses txaio.config.loop
        # directly -- pinned to the dead loop, those callbacks silently never
        # fire. Re-pointing it at the loop that's actually running fixes that
        # for both the first connect() and every reconnect after it, since
        # this process only ever runs one asyncio.run() for its whole life.
        txaio.config.loop = loop  # ty: ignore[unresolved-attribute]
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

        # labgrid.remote.client.start_session() (which this mirrors) awaits
        # `ready` with no timeout at all. Low-stakes for a one-shot CLI
        # command someone would just Ctrl-C, but this exporter awaits
        # connect() from an unattended reconnect loop -- if the WAMP-level
        # session handshake never completes after the transport opens
        # (plausible right after a coordinator restart, if crossbar accepts
        # the connection before its WAMP router is fully up), this would
        # otherwise hang forever and silently wedge the whole process, not
        # just this one reconnect attempt.
        await asyncio.wait_for(ready.wait(), timeout=30)
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

    def resources(self) -> list[Resource]:
        if self._session is None:
            raise RuntimeError("not connected: call connect() first")
        return [
            _convert_resource(labgrid_exporter, group, name, entry)
            for labgrid_exporter, groups in self._session.resources.items()
            for group, entries in groups.items()
            for name, entry in entries.items()
        ]

    async def reservations(self) -> list[Reservation]:
        if self._session is None:
            raise RuntimeError("not connected: call connect() first")
        # No push subscription for reservations in labgrid's WAMP protocol
        # (unlike places/resources) -- this is a real RPC every call.
        raw = await self._session.call("org.labgrid.coordinator.get_reservations")
        reservations = []
        for token, config in raw.items():
            kwargs = filter_dict(config, LabgridReservation, warn=False)
            # ty doesn't resolve __init__ for labgrid's legacy @attr.s-style
            # Reservation (same gap as ClientSession/txaio.config.loop above).
            res = LabgridReservation(token=token, **kwargs)  # ty: ignore[unknown-argument]
            reservations.append(_convert_reservation(res))
        return reservations

    def connected(self) -> bool:
        return self._session is not None and self._session.is_connected()
