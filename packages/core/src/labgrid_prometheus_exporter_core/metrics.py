"""Prometheus metric definitions derived from labgrid place state."""

from __future__ import annotations

from prometheus_client import Gauge

from labgrid_prometheus_exporter_core.interface import Place

PLACE_ACQUIRED = Gauge(
    "labgrid_place_acquired",
    "Whether a place is currently acquired (1) or free (0)",
    ["place"],
)
PLACE_CHANGED_TIMESTAMP = Gauge(
    "labgrid_place_changed_timestamp_seconds",
    "Unix timestamp of the last change to a place",
    ["place"],
)


def update_from_places(places: dict[str, Place]) -> None:
    """Refresh all gauges from a fresh snapshot of places.

    Gauges for places that have since disappeared are intentionally left in
    place for now (removing stale label sets is a known gap in this stub).
    """
    for name, place in places.items():
        PLACE_ACQUIRED.labels(place=name).set(1 if place.acquired else 0)
        PLACE_CHANGED_TIMESTAMP.labels(place=name).set(place.changed)
