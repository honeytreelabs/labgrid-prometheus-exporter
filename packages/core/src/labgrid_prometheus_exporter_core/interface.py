"""Contract between the exporter core and transport-specific backends.

Backends differ only in *how* they talk to a labgrid coordinator: labgrid's
WAMP-based protocol (releases up to 24.x) versus its gRPC-based protocol
(releases from 25.0 onwards). Everything else in this project depends only
on the types defined here, never on labgrid itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Place:
    """Version-agnostic snapshot of a labgrid place.

    Mirrors the subset of labgrid.remote.common.Place fields that have
    stayed stable across labgrid's WAMP and gRPC transports (releases 24.x
    through at least 26.0).
    """

    name: str
    aliases: frozenset[str]
    comment: str
    acquired: str | None
    acquired_resources: list[str]
    changed: float
    tags: dict[str, str]
    reservation: str | None = None


@dataclass(frozen=True, slots=True)
class Resource:
    """Version-agnostic snapshot of a labgrid resource.

    exporter/group/name are the outer dict keys of
    labgrid.remote.client.ClientSession.resources, not part of a
    ResourceEntry's own data; cls and avail come from ResourceEntry itself.
    Deliberately excludes ResourceEntry's params/extra/acquired -- no
    current documented need beyond availability.
    """

    exporter: str
    group: str
    name: str
    cls: str
    avail: bool


@dataclass(frozen=True, slots=True)
class Reservation:
    """Version-agnostic snapshot of a labgrid reservation.

    Deliberately excludes labgrid's reservation token: a fresh random
    10-character string generated per reservation request, unsuitable as a
    stable identity or Prometheus label (unbounded, ephemeral cardinality).
    `pending` collapses labgrid's 5-state ReservationState down to the one
    distinction this project's metrics need (state == waiting), so this
    module still has zero dependency on labgrid's own types.
    """

    owner: str
    created: float
    pending: bool


@runtime_checkable
class CoordinatorBackend(Protocol):
    """A persistent connection to a labgrid coordinator.

    An implementation owns exactly one connection for its lifetime and keeps
    an internally updated view of all places, so repeated places() calls
    (e.g. once per Prometheus scrape) are cheap and don't re-fetch the full
    state over the network.
    """

    async def connect(self) -> None:
        """Open the connection to the coordinator."""
        ...

    async def close(self) -> None:
        """Close the connection."""
        ...

    def places(self) -> dict[str, Place]:
        """Return the current snapshot of all places, keyed by name."""
        ...

    def resources(self) -> list[Resource]:
        """Return the current snapshot of all resources.

        Like places(), this is a cheap read of already-tracked local
        state -- labgrid subscribes to resource updates the same way it
        does for places, no extra network call needed here.
        """
        ...

    async def reservations(self) -> list[Reservation]:
        """Return the current list of reservations.

        Unlike places()/resources(), labgrid never pushes reservation
        updates -- this makes a real coordinator call every time, which is
        why it's async and the other two aren't.
        """
        ...

    def connected(self) -> bool:
        """Whether the connection to the coordinator is currently live.

        places() keeps returning the last-known snapshot even after the
        connection drops, so callers that care about staleness (e.g. the
        exporter's self-health metrics) need this separately.
        """
        ...
