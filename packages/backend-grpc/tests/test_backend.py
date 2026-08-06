"""GrpcCoordinatorBackend structurally satisfies the core CoordinatorBackend contract."""

from __future__ import annotations

from labgrid_prometheus_exporter_backend_grpc.backend import GrpcCoordinatorBackend
from labgrid_prometheus_exporter_core.interface import CoordinatorBackend


def test_backend_satisfies_protocol() -> None:
    assert isinstance(GrpcCoordinatorBackend("127.0.0.1:20408"), CoordinatorBackend)
