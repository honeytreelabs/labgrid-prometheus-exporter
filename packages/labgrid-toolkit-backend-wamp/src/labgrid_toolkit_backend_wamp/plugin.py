"""Argument wiring consumed by the labgrid-prometheus-exporter meta package.

Same shape as labgrid_toolkit_backend_grpc.plugin
(add_arguments, create_backend); see that module's docstring.
"""

from __future__ import annotations

import argparse
import os

from labgrid_toolkit_backend_wamp.backend import WampCoordinatorBackend


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--crossbar",
        default=os.environ.get("LG_CROSSBAR", "ws://127.0.0.1:20408/ws"),
        help="crossbar websocket URL (default: value from env variable LG_CROSSBAR, "
        "otherwise ws://127.0.0.1:20408/ws)",
    )
    parser.add_argument(
        "--crossbar-realm",
        default=os.environ.get("LG_CROSSBAR_REALM", "realm1"),
        help="crossbar realm (default: value from env variable LG_CROSSBAR_REALM, "
        "otherwise realm1)",
    )


def create_backend(args: argparse.Namespace) -> WampCoordinatorBackend:
    return WampCoordinatorBackend(args.crossbar, args.crossbar_realm)
