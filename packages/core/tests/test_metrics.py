"""Metric updates work from plain Place values, with no labgrid installed."""

from __future__ import annotations

import time

from labgrid_prometheus_exporter_core.interface import Place
from labgrid_prometheus_exporter_core.metrics import (
    COORDINATOR_CONNECTED,
    PLACE_ACQUIRED,
    PLACE_ACQUIRED_SECONDS,
    PLACE_CHANGED_TIMESTAMP,
    PLACE_TAG_INFO,
    PLACES_ACQUIRED_BY_USER,
    PLACES_LAST_UPDATE_TIMESTAMP,
    update_connection_health,
    update_from_places,
)


def _place(
    *,
    name: str = "example",
    acquired: str | None = None,
    changed: float = 1234.5,
    tags: dict[str, str] | None = None,
) -> Place:
    return Place(
        name=name,
        aliases=frozenset(),
        comment="",
        acquired=acquired,
        acquired_resources=[],
        changed=changed,
        tags=tags or {},
    )


def test_update_from_places_sets_gauges() -> None:
    update_from_places({"example": _place(acquired="host/user")})

    assert PLACE_ACQUIRED.labels(place="example")._value.get() == 1
    assert PLACE_CHANGED_TIMESTAMP.labels(place="example")._value.get() == 1234.5


def test_update_from_places_marks_released_place_as_zero() -> None:
    update_from_places({"example": _place(acquired=None)})

    assert PLACE_ACQUIRED.labels(place="example")._value.get() == 0


def test_update_from_places_removes_gauges_for_deleted_place() -> None:
    update_from_places({"temp": _place(name="temp", acquired="host/user")})
    assert ("temp",) in PLACE_ACQUIRED._metrics

    update_from_places({})

    assert ("temp",) not in PLACE_ACQUIRED._metrics
    assert ("temp",) not in PLACE_CHANGED_TIMESTAMP._metrics


def test_update_from_places_sets_tag_info() -> None:
    update_from_places({"tagged": _place(name="tagged", tags={"board": "rpi4"})})

    assert ("tagged", "board", "rpi4") in PLACE_TAG_INFO._metrics
    assert PLACE_TAG_INFO.labels(place="tagged", key="board", value="rpi4")._value.get() == 1


def test_update_from_places_removes_stale_tag_when_value_changes() -> None:
    update_from_places({"retag": _place(name="retag", tags={"usage": "ci"})})
    assert ("retag", "usage", "ci") in PLACE_TAG_INFO._metrics

    update_from_places({"retag": _place(name="retag", tags={"usage": "manual"})})

    assert ("retag", "usage", "ci") not in PLACE_TAG_INFO._metrics
    assert ("retag", "usage", "manual") in PLACE_TAG_INFO._metrics


def test_update_from_places_removes_tag_when_place_deleted() -> None:
    update_from_places({"gone": _place(name="gone", tags={"usage": "ci"})})
    assert ("gone", "usage", "ci") in PLACE_TAG_INFO._metrics

    update_from_places({})

    assert ("gone", "usage", "ci") not in PLACE_TAG_INFO._metrics


def test_update_from_places_sets_acquired_seconds_only_while_acquired() -> None:
    now = time.time()
    update_from_places({"held": _place(name="held", acquired="host/user", changed=now - 10)})

    assert ("held",) in PLACE_ACQUIRED_SECONDS._metrics
    assert PLACE_ACQUIRED_SECONDS.labels(place="held")._value.get() >= 10

    update_from_places({"held": _place(name="held", acquired=None, changed=now)})

    assert ("held",) not in PLACE_ACQUIRED_SECONDS._metrics


def test_update_from_places_counts_places_acquired_by_user() -> None:
    update_from_places(
        {
            "a": _place(name="a", acquired="host/alice"),
            "b": _place(name="b", acquired="host/alice"),
            "c": _place(name="c", acquired="host/bob"),
        }
    )

    assert PLACES_ACQUIRED_BY_USER.labels(user="alice")._value.get() == 2
    assert PLACES_ACQUIRED_BY_USER.labels(user="bob")._value.get() == 1

    update_from_places({"a": _place(name="a", acquired=None), "c": _place(name="c", acquired=None)})

    assert ("bob",) not in PLACES_ACQUIRED_BY_USER._metrics


def test_update_connection_health_sets_gauges() -> None:
    before = time.time()
    update_connection_health(True)

    assert COORDINATOR_CONNECTED._value.get() == 1
    assert PLACES_LAST_UPDATE_TIMESTAMP._value.get() >= before

    update_connection_health(False)

    assert COORDINATOR_CONNECTED._value.get() == 0
