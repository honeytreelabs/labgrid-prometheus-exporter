"""Argument wiring consumed by the labgrid-prometheus-exporter meta package.

Every backend package exposes this same shape (add_arguments, create_backend)
so the meta package's CLI can wire up whichever single backend is installed
without knowing anything about it up front.
"""

from __future__ import annotations

import argparse
import os

from labgrid_toolkit_backend_grpc.backend import GrpcCoordinatorBackend


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--coordinator",
        default=os.environ.get("LG_COORDINATOR", "127.0.0.1:20408"),
        help="coordinator HOST[:PORT] (default: value from env variable LG_COORDINATOR, "
        "otherwise 127.0.0.1:20408)",
    )


def create_backend(args: argparse.Namespace) -> GrpcCoordinatorBackend:
    return GrpcCoordinatorBackend(args.coordinator)
