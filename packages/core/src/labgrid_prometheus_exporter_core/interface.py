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
    reservation: str | None = None


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
