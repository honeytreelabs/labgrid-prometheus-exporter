"""End-to-end test: a real coordinator and a real exporter, driven via
labgrid-client -- see conftest.py for the fixtures and why this needs Docker
and isn't part of `make test`.
"""

from __future__ import annotations

from collections.abc import Callable

PLACE = "integration-test-place"


def test_acquired_place_and_tag_appear_in_metrics(
    labgrid_client: Callable[..., None],
    metric_value: Callable[..., float | None],
    wait_until: Callable[..., None],
) -> None:
    labgrid_client("-p", PLACE, "acquire")
    try:
        wait_until(lambda: metric_value("labgrid_place_acquired", place=PLACE) == 1.0)
        wait_until(lambda: metric_value("labgrid_place_acquire_total", place=PLACE) == 1.0)

        assert metric_value("labgrid_place_tag_info", place=PLACE, key="usage", value="ci") == 1.0
    finally:
        labgrid_client("-p", PLACE, "release")

    wait_until(lambda: metric_value("labgrid_place_acquired", place=PLACE) == 0.0)
    wait_until(lambda: metric_value("labgrid_place_release_total", place=PLACE) == 1.0)
