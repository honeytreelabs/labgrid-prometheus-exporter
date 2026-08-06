"""Backend discovery: exactly one installed backend is required."""

from __future__ import annotations

import pytest

from labgrid_prometheus_exporter import backends

# These tests can't rely on a *real* backend package being installed: the
# grpc and wamp backends conflict with each other (see the workspace root's
# [tool.uv] conflicts), so at most one is ever genuinely present, and which
# one depends on how the dev environment was last synced. Instead they
# monkeypatch _BACKENDS to point at modules that are always importable
# regardless of that choice (labgrid_prometheus_exporter_core, meta's own
# required dependency, and labgrid_prometheus_exporter itself), so the
# import-based logic in _installed_backends() is still exercised for real.


def test_resolve_backend_module_finds_the_installed_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(backends, "_BACKENDS", {"fake": "labgrid_prometheus_exporter_core"})

    assert backends.resolve_backend_module() == "labgrid_prometheus_exporter_core"


def test_resolve_backend_module_raises_when_none_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backends, "_BACKENDS", {"fake": "no_such_module_at_all"})

    with pytest.raises(RuntimeError, match="No labgrid-prometheus-exporter backend"):
        backends.resolve_backend_module()


def test_resolve_backend_module_raises_when_multiple_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        backends,
        "_BACKENDS",
        {
            "fake-a": "labgrid_prometheus_exporter_core",
            "fake-b": "labgrid_prometheus_exporter",
        },
    )

    with pytest.raises(RuntimeError, match="Multiple labgrid-prometheus-exporter backends"):
        backends.resolve_backend_module()
