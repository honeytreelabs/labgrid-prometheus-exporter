import argparse

from labgrid_prometheus_exporter_backend_grpc.backend import GrpcCoordinatorBackend
from labgrid_prometheus_exporter_backend_grpc.plugin import add_arguments, create_backend


def test_add_arguments_defaults() -> None:
    parser = argparse.ArgumentParser()
    add_arguments(parser)

    args = parser.parse_args([])

    assert args.coordinator == "127.0.0.1:20408"


def test_add_arguments_override() -> None:
    parser = argparse.ArgumentParser()
    add_arguments(parser)

    args = parser.parse_args(["--coordinator", "10.0.0.1:20408"])

    assert args.coordinator == "10.0.0.1:20408"


def test_create_backend_returns_grpc_backend() -> None:
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args(["--coordinator", "10.0.0.1:20408"])

    backend = create_backend(args)

    assert isinstance(backend, GrpcCoordinatorBackend)
