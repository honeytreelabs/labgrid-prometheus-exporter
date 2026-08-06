"""Command line entry point for labgrid-prometheus-exporter.

Delegates to whichever single transport backend is installed (see
labgrid_prometheus_exporter.backends).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib

from labgrid_prometheus_exporter_core.exporter import run

from labgrid_prometheus_exporter.backends import resolve_backend_module


def main() -> int:
    backend_module = importlib.import_module(resolve_backend_module())

    parser = argparse.ArgumentParser(prog="labgrid-prometheus-exporter")
    parser.add_argument("--http-port", type=int, default=9314, help="port to serve metrics on")
    parser.add_argument(
        "--poll-interval", type=float, default=5.0, help="seconds between metric refreshes"
    )
    backend_module.add_arguments(parser)
    args = parser.parse_args()

    backend = backend_module.create_backend(args)
    asyncio.run(run(backend, http_port=args.http_port, poll_interval=args.poll_interval))
    return 0
