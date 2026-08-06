"""Metric updates work from plain Place values, with no labgrid installed."""

from __future__ import annotations

from labgrid_prometheus_exporter_core.interface import Place
from labgrid_prometheus_exporter_core.metrics import (
    PLACE_ACQUIRED,
    PLACE_CHANGED_TIMESTAMP,
    update_from_places,
)


def test_update_from_places_sets_gauges() -> None:
    places = {
        "example": Place(
            name="example",
            aliases=frozenset(),
            comment="",
            acquired="host/user",
            acquired_resources=[],
            changed=1234.5,
        ),
    }

    update_from_places(places)

    assert PLACE_ACQUIRED.labels(place="example")._value.get() == 1
    assert PLACE_CHANGED_TIMESTAMP.labels(place="example")._value.get() == 1234.5


def test_update_from_places_marks_released_place_as_zero() -> None:
    places = {
        "example": Place(
            name="example",
            aliases=frozenset(),
            comment="",
            acquired=None,
            acquired_resources=[],
            changed=1234.5,
        ),
    }

    update_from_places(places)

    assert PLACE_ACQUIRED.labels(place="example")._value.get() == 0
