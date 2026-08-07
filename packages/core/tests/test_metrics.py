"""Metric updates work from plain Place values, with no labgrid installed."""

from __future__ import annotations

import time

from labgrid_prometheus_exporter_core.interface import Place, Reservation, Resource
from labgrid_prometheus_exporter_core.metrics import (
    COORDINATOR_CONNECTED,
    PLACE_ACQUIRE_TOTAL,
    PLACE_ACQUIRED,
    PLACE_ACQUIRED_SECONDS,
    PLACE_CHANGED_TIMESTAMP,
    PLACE_RELEASE_TOTAL,
    PLACE_TAG_INFO,
    PLACES_ACQUIRED_BY_USER,
    PLACES_LAST_UPDATE_TIMESTAMP,
    RESERVATION_WAIT_SECONDS,
    RESERVATIONS_PENDING,
    RESOURCE_AVAILABLE,
    update_connection_health,
    update_from_places,
    update_from_reservations,
    update_from_resources,
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


def _resource(
    *,
    exporter: str = "exp",
    group: str = "grp",
    name: str = "res",
    cls: str = "NetworkPowerPort",
    avail: bool,
) -> Resource:
    return Resource(exporter=exporter, group=group, name=name, cls=cls, avail=avail)


def _reservation(
    *, owner: str = "alice", created: float = 1000.0, pending: bool = True
) -> Reservation:
    return Reservation(owner=owner, created=created, pending=pending)


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


def test_update_from_places_counts_acquire_transition() -> None:
    update_from_places({"turnover-a": _place(name="turnover-a", acquired="host/user")})

    assert PLACE_ACQUIRE_TOTAL.labels(place="turnover-a")._value.get() == 1
    assert ("turnover-a",) not in PLACE_RELEASE_TOTAL._metrics


def test_update_from_places_does_not_double_count_steady_state() -> None:
    place = _place(name="turnover-b", acquired="host/user")
    update_from_places({"turnover-b": place})
    update_from_places({"turnover-b": place})

    assert PLACE_ACQUIRE_TOTAL.labels(place="turnover-b")._value.get() == 1


def test_update_from_places_counts_release_transition() -> None:
    update_from_places({"turnover-c": _place(name="turnover-c", acquired="host/user")})
    update_from_places({"turnover-c": _place(name="turnover-c", acquired=None)})

    assert PLACE_RELEASE_TOTAL.labels(place="turnover-c")._value.get() == 1


def test_update_from_places_never_acquired_place_has_no_release_total() -> None:
    update_from_places({"turnover-d": _place(name="turnover-d", acquired=None)})

    assert ("turnover-d",) not in PLACE_RELEASE_TOTAL._metrics


def test_update_from_places_accumulates_across_multiple_cycles() -> None:
    acquired = _place(name="turnover-e", acquired="host/user")
    released = _place(name="turnover-e", acquired=None)

    update_from_places({"turnover-e": acquired})
    update_from_places({"turnover-e": released})
    update_from_places({"turnover-e": acquired})
    update_from_places({"turnover-e": released})

    assert PLACE_ACQUIRE_TOTAL.labels(place="turnover-e")._value.get() == 2
    assert PLACE_RELEASE_TOTAL.labels(place="turnover-e")._value.get() == 2


def test_update_from_places_deletion_while_acquired_is_not_a_release() -> None:
    update_from_places({"turnover-f": _place(name="turnover-f", acquired="host/user")})

    update_from_places({})

    assert ("turnover-f",) not in PLACE_RELEASE_TOTAL._metrics


def test_update_from_places_acquire_total_survives_place_deletion() -> None:
    update_from_places({"turnover-g": _place(name="turnover-g", acquired="host/user")})
    assert PLACE_ACQUIRE_TOTAL.labels(place="turnover-g")._value.get() == 1

    update_from_places({})

    assert PLACE_ACQUIRE_TOTAL.labels(place="turnover-g")._value.get() == 1


def test_update_from_places_tracks_acquire_total_independently_per_place() -> None:
    update_from_places(
        {
            "turnover-h": _place(name="turnover-h", acquired="host/user"),
            "turnover-i": _place(name="turnover-i", acquired="host/user"),
        }
    )

    assert PLACE_ACQUIRE_TOTAL.labels(place="turnover-h")._value.get() == 1
    assert PLACE_ACQUIRE_TOTAL.labels(place="turnover-i")._value.get() == 1


def test_update_from_resources_sets_availability() -> None:
    update_from_resources(
        [
            _resource(exporter="exp", group="grp", name="avail-res", avail=True),
            _resource(exporter="exp", group="grp", name="unavail-res", avail=False),
        ]
    )

    assert (
        RESOURCE_AVAILABLE.labels(
            exporter="exp", group="grp", name="avail-res", cls="NetworkPowerPort"
        )._value.get()
        == 1
    )
    assert (
        RESOURCE_AVAILABLE.labels(
            exporter="exp", group="grp", name="unavail-res", cls="NetworkPowerPort"
        )._value.get()
        == 0
    )


def test_update_from_resources_removes_gauge_for_disappeared_resource() -> None:
    update_from_resources([_resource(exporter="exp", group="grp", name="temp-res", avail=True)])
    assert ("exp", "grp", "temp-res", "NetworkPowerPort") in RESOURCE_AVAILABLE._metrics

    update_from_resources([])

    assert ("exp", "grp", "temp-res", "NetworkPowerPort") not in RESOURCE_AVAILABLE._metrics


def test_update_from_resources_treats_cls_change_as_new_identity() -> None:
    update_from_resources(
        [_resource(exporter="exp", group="grp", name="retyped", cls="OldCls", avail=True)]
    )
    assert ("exp", "grp", "retyped", "OldCls") in RESOURCE_AVAILABLE._metrics

    update_from_resources(
        [_resource(exporter="exp", group="grp", name="retyped", cls="NewCls", avail=True)]
    )

    assert ("exp", "grp", "retyped", "OldCls") not in RESOURCE_AVAILABLE._metrics
    assert ("exp", "grp", "retyped", "NewCls") in RESOURCE_AVAILABLE._metrics


def test_update_from_reservations_counts_pending_and_oldest_wait() -> None:
    before = time.time()
    update_from_reservations(
        [
            _reservation(owner="alice", created=1000.0, pending=True),
            _reservation(owner="bob", created=900.0, pending=True),
        ]
    )

    assert RESERVATIONS_PENDING._value.get() == 2
    # Oldest (lowest created) among pending is used, not insertion order.
    wait = RESERVATION_WAIT_SECONDS._value.get()
    assert before - 900.0 <= wait < before - 900.0 + 5


def test_update_from_reservations_wait_seconds_is_zero_when_none_pending() -> None:
    update_from_reservations([])

    assert RESERVATIONS_PENDING._value.get() == 0
    assert RESERVATION_WAIT_SECONDS._value.get() == 0


def test_update_from_reservations_excludes_non_pending() -> None:
    update_from_reservations(
        [
            _reservation(owner="alice", created=1000.0, pending=False),
        ]
    )

    assert RESERVATIONS_PENDING._value.get() == 0


def test_update_connection_health_sets_gauges() -> None:
    before = time.time()
    update_connection_health(True)

    assert COORDINATOR_CONNECTED._value.get() == 1
    assert PLACES_LAST_UPDATE_TIMESTAMP._value.get() >= before

    update_connection_health(False)

    assert COORDINATOR_CONNECTED._value.get() == 0
