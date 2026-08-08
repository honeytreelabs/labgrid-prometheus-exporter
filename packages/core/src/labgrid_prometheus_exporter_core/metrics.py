"""Prometheus metric definitions derived from labgrid place state."""

from __future__ import annotations

import time

from prometheus_client import Counter, Gauge

from labgrid_prometheus_exporter_core.interface import Place, Reservation, Resource

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
PLACE_ACQUIRE_TOTAL = Counter(
    "labgrid_place_acquire_total",
    "Total number of times a place has transitioned from free to acquired",
    ["place"],
)
PLACE_RELEASE_TOTAL = Counter(
    "labgrid_place_release_total",
    "Total number of times a place has transitioned from acquired to free. "
    "A place being deleted while acquired does not count as a release.",
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
    "Whether this Prometheus exporter's connection to the labgrid coordinator is currently live",
)
PLACES_LAST_UPDATE_TIMESTAMP = Gauge(
    "labgrid_places_last_update_timestamp_seconds",
    "Unix timestamp of the last time place metrics were refreshed from the backend",
)
RESOURCE_AVAILABLE = Gauge(
    "labgrid_resource_available",
    "Whether a labgrid resource is currently available (1) or not (0). "
    "The labgrid_exporter label identifies the upstream labgrid exporter "
    "process that registered the resource, not this Prometheus exporter.",
    ["labgrid_exporter", "group", "name", "cls"],
)
RESERVATIONS_PENDING = Gauge(
    "labgrid_reservations_pending",
    "Number of reservations currently waiting for a place",
)
RESERVATION_WAIT_SECONDS = Gauge(
    "labgrid_reservation_wait_seconds",
    "How long the oldest pending reservation has been waiting, in seconds. 0 if none are pending.",
)

_previous_places: set[str] = set()
_previous_acquired_places: set[str] = set()
_previous_tags: set[tuple[str, str, str]] = set()
_previous_users: set[str] = set()
_previous_resources: set[tuple[str, str, str, str]] = set()


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

    # Deliberately not included in the cleanup loops below: these represent
    # historical totals, not current state, so unlike the gauges they are
    # not removed when a place is deleted (see PLACE_RELEASE_TOTAL's help
    # text for why a deletion isn't counted as a release either).
    for name in current_acquired_places - _previous_acquired_places:
        PLACE_ACQUIRE_TOTAL.labels(place=name).inc()
    for name in (_previous_acquired_places - current_acquired_places) & current_places:
        PLACE_RELEASE_TOTAL.labels(place=name).inc()

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


def update_from_resources(resources: list[Resource]) -> None:
    """Refresh labgrid_resource_available from a fresh snapshot of resources.

    Removes series for resources that have dropped out since the last call
    (labgrid exporter disconnected, resource removed), same reasoning as the
    place gauges in update_from_places(): availability is current state, not
    history, so a resource that no longer exists shouldn't keep reporting
    stale availability.

    The tracked identity is the full (labgrid_exporter, group, name, cls)
    tuple, matching all four labelnames, not just the 3-part
    (labgrid_exporter, group, name) logical identity -- removing a label
    series requires every label value, the same reason _previous_tags
    tracks (place, key, value) triples rather than (place, key) pairs. A
    resource's cls changing is therefore treated as its old identity
    disappearing and a new one appearing, exactly like a tag's value
    changing.
    """
    current: set[tuple[str, str, str, str]] = set()

    for r in resources:
        current.add((r.labgrid_exporter, r.group, r.name, r.cls))
        RESOURCE_AVAILABLE.labels(
            labgrid_exporter=r.labgrid_exporter, group=r.group, name=r.name, cls=r.cls
        ).set(1 if r.avail else 0)

    for labgrid_exporter, group, name, cls in _previous_resources - current:
        RESOURCE_AVAILABLE.remove(labgrid_exporter, group, name, cls)

    _previous_resources.clear()
    _previous_resources.update(current)


def update_from_reservations(reservations: list[Reservation]) -> None:
    """Refresh the reservation queue gauges from a fresh list of reservations.

    Unlike the place/resource gauges, there's no removal step here: these
    are unlabeled Gauges (a single global value each), and prometheus_client
    gives unlabeled Gauges a value from process start with no equivalent of
    .remove() to make them disappear -- so "nothing pending" is represented
    as 0, not absence.
    """
    pending = [r for r in reservations if r.pending]

    RESERVATIONS_PENDING.set(len(pending))
    RESERVATION_WAIT_SECONDS.set(time.time() - min(r.created for r in pending) if pending else 0)


def update_connection_health(connected: bool) -> None:
    """Refresh the exporter's self-health gauges.

    Called once per poll iteration regardless of whether the backend's data
    changed, so staleness is visible even when the coordinator is unreachable
    (places() keeps returning its last-known snapshot rather than raising).
    """
    COORDINATOR_CONNECTED.set(1 if connected else 0)
    PLACES_LAST_UPDATE_TIMESTAMP.set(time.time())
