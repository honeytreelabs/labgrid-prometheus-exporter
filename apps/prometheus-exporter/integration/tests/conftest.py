"""Fixtures for docker-compose-based integration tests.

These bring up a real labgrid coordinator and a real
labgrid-prometheus-exporter container, drive the coordinator via
`labgrid-client` (already available in whichever backend variant's venv is
active -- see the Makefile), and scrape this Prometheus exporter's real
HTTP endpoint.
Requires Docker; not run by `make test`. See `make test-integration`.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time
from collections.abc import Callable, Iterator

import httpx
import pytest
from prometheus_client.parser import text_string_to_metric_families

ROOT = pathlib.Path(__file__).resolve().parents[4]
VARIANT = os.environ.get("LG_PROMETHEUS_EXPORTER_TEST_VARIANT", "grpc")
COMPOSE_FILE = ROOT / "apps" / "prometheus-exporter" / "docker" / f"compose.{VARIANT}.yml"


def _compose(*args: str) -> None:
    """Run a docker compose command, streaming its output straight through.

    Deliberately doesn't capture stdout/stderr: `up`/`down`/`build` failures
    need to be visible directly, not swallowed into an unprinted
    CompletedProcess. Only the port lookup below needs captured output.
    """
    subprocess.run(["docker", "compose", "-f", str(COMPOSE_FILE), *args], cwd=ROOT, check=True)


def _published_address(service: str, container_port: int) -> str:
    """Host address Docker actually bound `service`'s container_port to.

    The compose files don't pin fixed host ports specifically so this never
    collides with anything else already using 20408/9314 on the host (a real
    labgrid coordinator, another compose project, etc.) -- Docker picks a
    free ephemeral port, and we discover it here instead of assuming one.
    """
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "port", service, str(container_port)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    host, _, port = result.stdout.strip().rpartition(":")
    if host in ("", "0.0.0.0", "::"):
        host = "127.0.0.1"
    return f"{host}:{port}"


@pytest.fixture(scope="session")
def compose_stack() -> Iterator[dict[str, str]]:
    """Build and start the coordinator + Prometheus exporter stack for one test session."""
    try:
        _compose("up", "-d", "--build", "--wait")
        yield {
            "coordinator": _published_address("coordinator", 20408),
            "prometheus_exporter_metrics": _published_address("prometheus-exporter", 9314),
        }
    finally:
        # In the same try/finally as `up`, not after it: if `up` itself
        # fails partway (as it can on a port conflict), whatever it did
        # manage to create must still be torn down, or it leaks and can
        # cause the exact same conflict on the next run.
        _compose("down", "-v")


@pytest.fixture
def restart_coordinator(compose_stack: dict[str, str]) -> Callable[[], None]:
    """Restart just the coordinator container, simulating an outage.

    Leaves the Prometheus exporter container running throughout -- this is
    meant to exercise its own reconnect logic, not Compose restarting it for
    us. A coordinator process restart and a network partition look
    identical from the Prometheus exporter's side (connection drops, then
    becomes reachable again), so this one mechanism covers both.
    """

    def restart() -> None:
        _compose("restart", "coordinator")

    return restart


@pytest.fixture
def restart_labgrid_exporter(compose_stack: dict[str, str]) -> Callable[[], None]:
    """Restart the labgrid-exporter container, forcing a fresh registration.

    Needed because labgrid-exporter -- unlike this project's own Prometheus
    exporter -- is unmodified upstream labgrid code with no reconnect logic
    of its own: confirmed via `docker compose logs labgrid-exporter` that
    after a coordinator restart it logs "coordinator became unavailable: Cancelling
    all calls" and never reconnects, permanently orphaning its resource
    registration. Since compose_stack is session-scoped and shared with
    test_reconnect.py (which restarts the coordinator), test_resources.py
    can't just assume labgrid-exporter is still connected -- it has to force
    a fresh connection itself rather than depend on test execution order.
    """

    def restart() -> None:
        _compose("restart", "labgrid-exporter")

    return restart


_LABGRID_CLIENT_SCRIPT = (
    # labgrid-client is invoked via `python -c` instead of the console
    # script directly so we can set an event loop before importing
    # labgrid.remote.client: on labgrid < 25.0, that module runs
    # `txaio.config.loop = asyncio.get_event_loop()` at import time, which
    # raises on Python >= 3.14 with no loop already set for the thread (the
    # same bug root conftest.py works around for our own test process --
    # this subprocess is a separate interpreter that fix never reaches).
    # Harmless no-op for the grpc variant, whose client.py has no such line.
    "import asyncio, sys; "
    "asyncio.set_event_loop(asyncio.new_event_loop()); "
    "from labgrid.remote.client import main; "
    "sys.exit(main())"
)


@pytest.fixture
def labgrid_client(compose_stack: dict[str, str]) -> Callable[..., None]:
    """Run `labgrid-client <args>` against the stack's coordinator.

    compose_stack is still a required dependency (ensures the stack is up
    before this runs), but its cached "coordinator" address is deliberately
    not used here: it's captured once, when this fixture is first set up,
    and a mid-test restart_coordinator() call can happen after that --
    reusing a stale address is exactly what broke the reconnect test.
    Re-resolving on every call is cheap and removes the assumption
    entirely, regardless of whether the address actually changes underneath.
    """

    def run(*args: str) -> None:
        address = _published_address("coordinator", 20408)
        env = os.environ.copy()
        if VARIANT == "grpc":
            env["LG_COORDINATOR"] = address
        else:
            env["LG_CROSSBAR"] = f"ws://{address}/ws"
        subprocess.run([sys.executable, "-c", _LABGRID_CLIENT_SCRIPT, *args], env=env, check=True)

    return run


@pytest.fixture
def scrape_metrics(compose_stack: dict[str, str]) -> Callable[[], str]:
    """Return this Prometheus exporter's current /metrics text."""
    url = f"http://{compose_stack['prometheus_exporter_metrics']}/metrics"

    def get() -> str:
        return httpx.get(url, timeout=5.0).text

    return get


@pytest.fixture
def metric_value(scrape_metrics: Callable[[], str]) -> Callable[..., float | None]:
    """Look up a single sample's value by metric name and labels, or None.

    Matches on each sample's own name, not the family's -- for a Counter,
    prometheus_client's parser groups the _total and _created series under
    one family whose .name has the _total suffix stripped (e.g. family.name
    "labgrid_place_acquire" for the sample named
    "labgrid_place_acquire_total"). Matching on family.name instead of
    sample.name meant this could never find a Counter by its real exposed
    name, silently returning None regardless of the actual value -- worked
    fine for Gauges (family.name == sample.name there) and was invisible in
    a manual `curl | grep`, since grep matches the raw line text, not this
    parsed family/sample structure.
    """

    def get(name: str, **labels: str) -> float | None:
        for family in text_string_to_metric_families(scrape_metrics()):
            for sample in family.samples:
                if sample.name != name:
                    continue
                if all(sample.labels.get(k) == v for k, v in labels.items()):
                    return sample.value
        return None

    return get


@pytest.fixture
def wait_until() -> Callable[..., None]:
    """Poll a predicate until it's true, or raise after a timeout.

    Needed because this Prometheus exporter only refreshes on its own poll
    interval (set short via --poll-interval in the compose files), so a
    change made through labgrid_client isn't visible in scrape_metrics()
    immediately.
    """

    def wait(
        predicate: Callable[[], bool], *, timeout: float = 15.0, interval: float = 0.5
    ) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(interval)
        raise AssertionError("condition not met before timeout")

    return wait
