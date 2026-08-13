"""This Prometheus exporter must recover on its own after the coordinator
becomes briefly unreachable (a restart during a deployment, a network
blip, ...) -- see conftest.py for why `restart_coordinator` simulates both
the same way, and exporter._poll's docstring for why this isn't free: no
labgrid ClientSession reconnects on its own.
"""

from __future__ import annotations

from collections.abc import Callable

PLACE = "integration-test-place"


def test_prometheus_exporter_reconnects_after_coordinator_restart(
    labgrid_client: Callable[..., None],
    metric_value: Callable[..., float | None],
    restart_coordinator: Callable[[], None],
    wait_until: Callable[..., None],
) -> None:
    labgrid_client("-p", PLACE, "acquire")
    wait_until(lambda: metric_value("labgrid_place_acquired", place=PLACE) == 1.0)
    labgrid_client("-p", PLACE, "release")

    restart_coordinator()

    # Generous timeouts: a real outage-then-recovery cycle, not just a
    # local state change -- the coordinator container has to actually stop,
    # come back up, and get rediscovered by this Prometheus exporter's own
    # poll loop.
    wait_until(lambda: metric_value("labgrid_coordinator_connected") == 0.0, timeout=45.0)
    wait_until(lambda: metric_value("labgrid_coordinator_connected") == 1.0, timeout=60.0)

    # Functional recovery, not just the connectivity flag: the coordinator
    # restarts with a fresh copy of the fixture (see docker-compose.*.yml),
    # so this deliberately re-acquires rather than expecting the pre-restart
    # acquisition to have survived -- what actually matters is that this
    # Prometheus exporter keeps correctly tracking new operations after
    # reconnecting.
    labgrid_client("-p", PLACE, "acquire")
    try:
        wait_until(lambda: metric_value("labgrid_place_acquired", place=PLACE) == 1.0)
    finally:
        labgrid_client("-p", PLACE, "release")
