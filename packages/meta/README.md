# labgrid-prometheus-exporter

The installable entry point for labgrid-prometheus-exporter. This package
owns the `labgrid-prometheus-exporter` command but contains no
transport-specific code itself — install it with the extra matching your
coordinator's labgrid version:

```sh
# coordinator running labgrid >= 25.0 (gRPC)
pip install labgrid-prometheus-exporter[grpc]

# coordinator running labgrid <= 24.x (WAMP)
pip install labgrid-prometheus-exporter[wamp]
```

Install exactly one extra. At startup, the command discovers which backend
is importable and refuses to run if it finds zero or more than one — see
`labgrid_prometheus_exporter.backends`. This is a runtime check: `pip` has
no first-class way to declare that two extras are mutually exclusive, so
installing both in the same environment via plain `pip` is still possible,
and the command errors clearly rather than silently picking one.

Within *this* repository's `uv` workspace specifically, there's a second,
earlier line of defense: `backend-grpc` and `backend-wamp` require
incompatible `labgrid` version ranges, and are declared as conflicting
workspace members (`[tool.uv] conflicts` in the root `pyproject.toml`), so
`uv sync` itself refuses to install both. That's a `uv`-workspace-specific,
sync-time mechanism though — it doesn't help someone installing published
wheels with plain `pip`, which is why the runtime check above still exists
as the real, universal enforcement.
