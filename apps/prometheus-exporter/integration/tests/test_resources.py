"""Resource availability against a real labgrid exporter process.

Unlike places, resource availability isn't driven by labgrid_client at all
-- it comes from a completely separate labgrid-exporter container (see
apps/prometheus-exporter/docker/compose.grpc.yml/apps/prometheus-exporter/docker/compose.wamp.yml) registering the resource
in apps/prometheus-exporter/integration/tests/fixtures/labgrid-exporter.yaml with the coordinator.
That resource (NetworkService) deliberately never needs real hardware or a
`dut` container to report available -- see the fixture file for why.
"""

from __future__ import annotations

from collections.abc import Callable


def test_resource_availability_reported(
    metric_value: Callable[..., float | None],
    restart_labgrid_exporter: Callable[[], None],
    wait_until: Callable[..., None],
) -> None:
    # compose_stack is session-scoped and shared with test_reconnect.py,
    # which restarts the coordinator -- labgrid-exporter has no reconnect
    # logic of its own (see restart_labgrid_exporter's docstring), so if
    # that ran first, its registration from initial startup is already gone
    # for good by the time this test runs. Force a fresh connection rather
    # than depend on test execution order.
    restart_labgrid_exporter()

    # Not matching on `labgrid_exporter` (whatever identity string the
    # labgrid exporter process registers itself with, not worth pinning
    # down) or `name` (its exact default for a single resource in a group
    # isn't confirmed) -- group + cls alone already uniquely identifies
    # this one resource in the fixture data.
    #
    # Generous timeout: a real container restart + reconnect + registration
    # cycle, not just a local state change -- same reasoning as
    # test_reconnect.py's generous timeouts.
    wait_until(
        lambda: (
            metric_value(
                "labgrid_resource_available",
                group="integration-test-group",
                cls="NetworkService",
            )
            == 1.0
        ),
        timeout=45.0,
    )
