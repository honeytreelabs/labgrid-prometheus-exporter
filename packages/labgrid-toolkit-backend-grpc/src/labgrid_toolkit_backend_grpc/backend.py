"""CoordinatorBackend implementation for labgrid's gRPC coordinator protocol."""

from __future__ import annotations

import asyncio

from labgrid.remote.client import ClientSession
from labgrid.remote.common import Place as LabgridPlace
from labgrid.remote.common import Reservation as LabgridReservation
from labgrid.remote.common import ReservationState, ResourceEntry
from labgrid.remote.generated import labgrid_coordinator_pb2
from labgrid_toolkit_core.interface import Place, Reservation, Resource


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


class GrpcCoordinatorBackend:
    """Talks to a labgrid >= 25.0 coordinator over gRPC.

    Wraps labgrid's own ClientSession instead of reimplementing the
    protocol: since only one labgrid version is ever installed alongside
    this backend, there's no version conflict to work around in-process.
    """

    def __init__(self, address: str, *, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._address = address
        self._loop = loop
        self._session: ClientSession | None = None

    async def connect(self) -> None:
        loop = self._loop or asyncio.get_running_loop()
        # ty doesn't resolve __init__ for labgrid's legacy @attr.s-style ClientSession.
        self._session = ClientSession(self._address, loop)  # ty: ignore[too-many-positional-arguments]
        await self._session.start()

    async def close(self) -> None:
        if self._session is None:
            return
        await self._session.stop()
        await self._session.close()
        self._session = None

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
        request = labgrid_coordinator_pb2.GetReservationsRequest()
        response = await self._session.stub.GetReservations(request)
        return [_convert_reservation(LabgridReservation.from_pb2(r)) for r in response.reservations]

    def connected(self) -> bool:
        return self._session is not None and not self._session.stopping.is_set()
