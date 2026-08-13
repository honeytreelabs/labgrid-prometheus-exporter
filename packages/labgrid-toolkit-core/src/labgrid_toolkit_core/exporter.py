"""Wires a CoordinatorBackend to a Prometheus HTTP endpoint."""

from __future__ import annotations

import asyncio
import logging

from prometheus_client import start_http_server

from labgrid_toolkit_core.interface import CoordinatorBackend
from labgrid_toolkit_core.metrics import (
    update_connection_health,
    update_from_places,
    update_from_reservations,
    update_from_resources,
)

logger = logging.getLogger(__name__)


async def _poll(backend: CoordinatorBackend) -> None:
    """Reconnect if the connection dropped, then refresh metrics.

    Neither labgrid transport's ClientSession reconnects on its own after a
    connection drops (coordinator restart, network blip, ...) -- once the
    underlying stream/session dies, it's done for good. Reconnection is this
    exporter's responsibility, not something inherited from labgrid.

    On a failed reconnect attempt, deliberately skips update_from_places():
    a freshly (re)constructed session's places() is empty until it finishes
    an initial sync, and feeding that through would make the diff-based
    cleanup in update_from_places() wipe every place's metrics just because
    the coordinator is briefly unreachable. update_connection_health() still
    runs either way, so staleness stays visible and the poll loop's own
    liveness stays visible even while the coordinator is down.
    """
    if not backend.connected():
        logger.warning("lost connection to coordinator, reconnecting")
        # Report the drop the moment it's detected, not only if the
        # reconnect attempt below also fails: a reconnect that succeeds on
        # its first try within this same poll cycle would otherwise fall
        # through to the update_connection_health() call at the end of this
        # function with connected() already true again, so the gauge would
        # go straight from 1 to 1 -- silently skipping a disconnect that
        # genuinely happened, just because it also genuinely resolved
        # quickly. Confirmed via a live trace: a coordinator restart whose
        # first reconnect attempt fails (e.g. a transient DNS blip) does
        # show a real 0 here; one whose first attempt immediately succeeds
        # never did, before this fix.
        update_connection_health(False)
        await backend.close()
        try:
            await backend.connect()
        except Exception:
            logger.exception("reconnect failed, will retry next poll")
            return
        else:
            # Without this, a successful reconnect is silent: logs would
            # show "lost connection... reconnecting" and then nothing,
            # which is genuinely ambiguous between "it recovered" and "it's
            # stuck" -- exactly the gap that made a real transient DNS
            # resolution failure (Docker's embedded DNS briefly not
            # resolving the coordinator hostname right after a container
            # restart) hard to distinguish from a hang while debugging this.
            logger.warning("reconnected to coordinator")

    update_from_places(backend.places())
    update_from_resources(backend.resources())
    try:
        update_from_reservations(await backend.reservations())
    except Exception:
        # A real, independent network call (unlike places()/resources(),
        # which just read already-tracked local state) -- one failure here
        # shouldn't prevent place/resource metrics from updating this cycle.
        logger.exception("failed to fetch reservations, will retry next poll")
    update_connection_health(backend.connected())


async def run(backend: CoordinatorBackend, *, http_port: int, poll_interval: float) -> None:
    """Connect the backend, serve metrics, and refresh them until cancelled."""
    await backend.connect()
    try:
        start_http_server(http_port)
        logger.info("serving metrics on :%d, polling every %.1fs", http_port, poll_interval)
        while True:
            await _poll(backend)
            await asyncio.sleep(poll_interval)
    finally:
        await backend.close()
