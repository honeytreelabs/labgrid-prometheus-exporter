"""Wires a CoordinatorBackend to a Prometheus HTTP endpoint."""

from __future__ import annotations

import asyncio
import logging

from prometheus_client import start_http_server

from labgrid_prometheus_exporter_core.interface import CoordinatorBackend
from labgrid_prometheus_exporter_core.metrics import update_connection_health, update_from_places

logger = logging.getLogger(__name__)


async def run(backend: CoordinatorBackend, *, http_port: int, poll_interval: float) -> None:
    """Connect the backend, serve metrics, and refresh them until cancelled."""
    await backend.connect()
    try:
        start_http_server(http_port)
        logger.info("serving metrics on :%d, polling every %.1fs", http_port, poll_interval)
        while True:
            update_from_places(backend.places())
            update_connection_health(backend.connected())
            await asyncio.sleep(poll_interval)
    finally:
        await backend.close()
