"""Prometheus metric definitions derived from labgrid place state."""

from __future__ import annotations

import time

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
PLACE_ACQUIRED_SECONDS = Gauge(
    "labgrid_place_acquired_seconds",
    "How long a place has been continuously acquired. Absent while the place is free.",
    ["place"],
)
PLACES_ACQUIRED_BY_USER = Gauge(
    "labgrid_places_acquired_by_user",
    "Number of places currently acquired by a user. Absent for users holding none.",
    ["user"],
)
PLACE_TAG_INFO = Gauge(
    "labgrid_place_tag_info",
    "Presence of a labgrid place tag: one series per (place, tag key). Value is always 1.",
    ["place", "key", "value"],
)
COORDINATOR_CONNECTED = Gauge(
    "labgrid_coordinator_connected",
    "Whether the exporter's connection to the labgrid coordinator is currently live",
)
PLACES_LAST_UPDATE_TIMESTAMP = Gauge(
    "labgrid_places_last_update_timestamp_seconds",
    "Unix timestamp of the last time place metrics were refreshed from the backend",
)

_previous_places: set[str] = set()
_previous_acquired_places: set[str] = set()
_previous_tags: set[tuple[str, str, str]] = set()
_previous_users: set[str] = set()


def update_from_places(places: dict[str, Place]) -> None:
    """Refresh all place-derived gauges from a fresh snapshot of places.

    Removes series for places, tags, and users that have dropped out of the
    snapshot since the last call, so a gauge never keeps reporting state for
    something that no longer exists or no longer applies (e.g. a place that
    was deleted, released, or had a tag removed).
    """
    current_places = set(places)
    current_acquired_places: set[str] = set()
    current_tags: set[tuple[str, str, str]] = set()
    users: dict[str, int] = {}

    for name, place in places.items():
        PLACE_ACQUIRED.labels(place=name).set(1 if place.acquired else 0)
        PLACE_CHANGED_TIMESTAMP.labels(place=name).set(place.changed)

        for key, value in place.tags.items():
            current_tags.add((name, key, value))
            PLACE_TAG_INFO.labels(place=name, key=key, value=value).set(1)

        if place.acquired:
            current_acquired_places.add(name)
            PLACE_ACQUIRED_SECONDS.labels(place=name).set(time.time() - place.changed)

            user = place.acquired.split("/", 1)[-1]
            users[user] = users.get(user, 0) + 1

    for user, count in users.items():
        PLACES_ACQUIRED_BY_USER.labels(user=user).set(count)

    for name in _previous_places - current_places:
        PLACE_ACQUIRED.remove(name)
        PLACE_CHANGED_TIMESTAMP.remove(name)
    for name in _previous_acquired_places - current_acquired_places:
        PLACE_ACQUIRED_SECONDS.remove(name)
    for name, key, value in _previous_tags - current_tags:
        PLACE_TAG_INFO.remove(name, key, value)
    for user in _previous_users - set(users):
        PLACES_ACQUIRED_BY_USER.remove(user)

    _previous_places.clear()
    _previous_places.update(current_places)
    _previous_acquired_places.clear()
    _previous_acquired_places.update(current_acquired_places)
    _previous_tags.clear()
    _previous_tags.update(current_tags)
    _previous_users.clear()
    _previous_users.update(users)


def update_connection_health(connected: bool) -> None:
    """Refresh the exporter's self-health gauges.

    Called once per poll iteration regardless of whether the backend's data
    changed, so staleness is visible even when the coordinator is unreachable
    (places() keeps returning its last-known snapshot rather than raising).
    """
    COORDINATOR_CONNECTED.set(1 if connected else 0)
    PLACES_LAST_UPDATE_TIMESTAMP.set(time.time())
