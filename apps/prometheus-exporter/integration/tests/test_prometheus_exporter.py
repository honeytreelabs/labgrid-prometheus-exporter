"""End-to-end test: a real coordinator and a real Prometheus exporter,
driven via labgrid-client -- see conftest.py for the fixtures and why this
needs Docker and isn't part of `make test`.
"""

from __future__ import annotations

from collections.abc import Callable

PLACE = "integration-test-place"


def test_acquired_place_and_tag_appear_in_metrics(
    labgrid_client: Callable[..., None],
    metric_value: Callable[..., float | None],
    wait_until: Callable[..., None],
) -> None:
    # labgrid_place_acquire_total/release_total accumulate for the whole
    # session-scoped Prometheus exporter process, shared with
    # test_reconnect.py and test_reservations.py acquiring/releasing this
    # same fixture place -- assert on the increase this test causes, not an
    # absolute value, since nothing guarantees this test runs before the
    # other two.
    acquire_total_before = metric_value("labgrid_place_acquire_total", place=PLACE) or 0
    release_total_before = metric_value("labgrid_place_release_total", place=PLACE) or 0

    labgrid_client("-p", PLACE, "acquire")
    try:
        wait_until(lambda: metric_value("labgrid_place_acquired", place=PLACE) == 1.0)
        wait_until(
            lambda: (
                (metric_value("labgrid_place_acquire_total", place=PLACE) or 0)
                == acquire_total_before + 1
            )
        )

        assert metric_value("labgrid_place_tag_info", place=PLACE, key="usage", value="ci") == 1.0
    finally:
        labgrid_client("-p", PLACE, "release")

    wait_until(lambda: metric_value("labgrid_place_acquired", place=PLACE) == 0.0)
    wait_until(
        lambda: (
            (metric_value("labgrid_place_release_total", place=PLACE) or 0)
            == release_total_before + 1
        )
    )
