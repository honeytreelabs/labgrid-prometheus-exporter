import argparse

from labgrid_prometheus_exporter_backend_wamp.backend import WampCoordinatorBackend
from labgrid_prometheus_exporter_backend_wamp.plugin import add_arguments, create_backend


def test_add_arguments_defaults() -> None:
    parser = argparse.ArgumentParser()
    add_arguments(parser)

    args = parser.parse_args([])

    assert args.crossbar == "ws://127.0.0.1:20408/ws"
    assert args.crossbar_realm == "realm1"


def test_add_arguments_override() -> None:
    parser = argparse.ArgumentParser()
    add_arguments(parser)

    args = parser.parse_args(["--crossbar", "ws://10.0.0.1:20408/ws", "--crossbar-realm", "other"])

    assert args.crossbar == "ws://10.0.0.1:20408/ws"
    assert args.crossbar_realm == "other"


def test_create_backend_returns_wamp_backend() -> None:
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args([])

    backend = create_backend(args)

    assert isinstance(backend, WampCoordinatorBackend)
