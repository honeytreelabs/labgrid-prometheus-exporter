"""CoordinatorBackend implementation for labgrid's gRPC coordinator protocol."""

from __future__ import annotations

import asyncio

from labgrid.remote.client import ClientSession
from labgrid.remote.common import Place as LabgridPlace
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

    def connected(self) -> bool:
        return self._session is not None and not self._session.stopping.is_set()
