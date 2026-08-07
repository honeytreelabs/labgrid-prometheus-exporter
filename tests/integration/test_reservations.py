"""Reservation queue metrics against a real coordinator.

Unlike places/resources, labgrid never pushes reservation updates -- see
CoordinatorBackend.reservations()'s docstring -- so this is also the only
integration coverage that actually proves the real per-poll RPC call works
against both transports, not just the unit-tested aggregation logic.
"""

from __future__ import annotations

from collections.abc import Callable

PLACE = "integration-test-place"


def test_reservation_appears_pending_until_place_is_freed(
    labgrid_client: Callable[..., None],
    metric_value: Callable[..., float | None],
    wait_until: Callable[..., None],
) -> None:
    # Take the only place matching `usage=ci` so a reservation against that
    # same filter has nothing free to allocate to, and must stay pending.
    labgrid_client("-p", PLACE, "acquire")
    try:
        labgrid_client("reserve", "--prio", "0", "usage=ci")

        wait_until(lambda: metric_value("labgrid_reservations_pending") == 1.0)
        assert (metric_value("labgrid_reservation_wait_seconds") or 0) > 0
    finally:
        # Freeing the place lets the coordinator's scheduler allocate the
        # reservation, moving it out of "pending" -- simpler than capturing
        # and cancelling the reservation's token explicitly. The allocated
        # (but never acquired) reservation is left to expire on its own
        # (labgrid's default reservation timeout), which is harmless: the
        # whole coordinator container is torn down at the end of the test
        # session anyway.
        labgrid_client("-p", PLACE, "release")

    wait_until(lambda: metric_value("labgrid_reservations_pending") == 0.0)
