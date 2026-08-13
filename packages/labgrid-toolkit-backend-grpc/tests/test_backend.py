"""GrpcCoordinatorBackend structurally satisfies the core CoordinatorBackend contract."""

from __future__ import annotations

from labgrid_toolkit_backend_grpc.backend import GrpcCoordinatorBackend
from labgrid_toolkit_core.interface import CoordinatorBackend


def test_backend_satisfies_protocol() -> None:
    assert isinstance(GrpcCoordinatorBackend("127.0.0.1:20408"), CoordinatorBackend)


def test_backend_not_connected_before_connect() -> None:
    assert GrpcCoordinatorBackend("127.0.0.1:20408").connected() is False
