"""Discovers which single transport backend is installed.

Each backend package exposes a `<package>.plugin` module with
`add_arguments(parser)` and `create_backend(args)` functions (see
labgrid_toolkit_backend_grpc.plugin for the shape). Exactly one
backend is expected to be installed at a time; pip has no built-in way to
declare that two extras are mutually exclusive, so this is enforced here at
runtime instead.
"""

from __future__ import annotations

import importlib

_BACKENDS = {
    "grpc": "labgrid_toolkit_backend_grpc.plugin",
    "wamp": "labgrid_toolkit_backend_wamp.plugin",
}


def _installed_backends() -> list[str]:
    installed = []
    for extra, module_name in _BACKENDS.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            continue
        installed.append(extra)
    return installed


def resolve_backend_module() -> str:
    """Return the plugin module path of the single installed backend.

    Raises RuntimeError if zero or more than one backend is installed.
    """
    installed = _installed_backends()

    if not installed:
        raise RuntimeError(
            "No labgrid-prometheus-exporter backend is installed. Install the extra "
            "matching your coordinator's labgrid version, e.g. "
            "'pip install labgrid-prometheus-exporter[grpc]'."
        )

    if len(installed) > 1:
        names = ", ".join(f"labgrid-toolkit-backend-{extra}" for extra in sorted(installed))
        raise RuntimeError(
            f"Multiple labgrid-prometheus-exporter backends are installed ({names}), but "
            "only one may be installed at a time. Uninstall the ones you don't need."
        )

    return _BACKENDS[installed[0]]
