# labgrid-prometheus-exporter

Labgrid Framework Prometheus Exporter.

Labgrid's coordinator protocol changed from WAMP (releases up to 24.x) to
gRPC (releases from 25.0 onwards) as a hard, backwards-incompatible break.
Since one exporter deployment only ever talks to one coordinator whose
labgrid version is known in advance, this project is split into a
transport-agnostic core and one backend package per labgrid protocol
generation, rather than trying to support every transport in one process.

## Layout

This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/):

- `packages/core` (`labgrid-prometheus-exporter-core`) — Prometheus metric
  definitions, HTTP server wiring, and the `CoordinatorBackend` contract.
  Has no dependency on `labgrid` itself.
- `packages/backend-grpc` (`labgrid-prometheus-exporter-backend-grpc`) —
  implements `CoordinatorBackend` for labgrid's gRPC protocol (labgrid
  >= 25.0) by wrapping labgrid's own `ClientSession`. A pure library, no
  console script.
- `packages/backend-wamp` (`labgrid-prometheus-exporter-backend-wamp`) —
  the same, for labgrid's WAMP/crossbar protocol (labgrid < 25.0).
- `packages/meta` (`labgrid-prometheus-exporter`) — the package end users
  actually install. Owns the `labgrid-prometheus-exporter` console script
  and discovers, at runtime, whichever single backend extra was installed.

`backend-grpc` and `backend-wamp` require incompatible `labgrid` ranges, so
they're declared as conflicting workspace members
([tool.uv] conflicts in this file's pyproject.toml): `uv` refuses to sync
both into the same environment. That's enforced at sync time, on top of the
runtime check in `labgrid_prometheus_exporter.backends` — see
`packages/meta/README.md`.

## Installation

Sync only `core`, `meta`, and the one backend matching your coordinator's
labgrid version — a plain `uv sync` at the repository root will fail
because it would otherwise need both backends at once:

```sh
uv sync --package labgrid-prometheus-exporter-core \
        --package labgrid-prometheus-exporter \
        --package labgrid-prometheus-exporter-backend-grpc  # or -backend-wamp
```

## Usage

Run the exporter command:

```sh
uv run --no-sync labgrid-prometheus-exporter --coordinator 127.0.0.1:20408   # grpc
uv run --no-sync labgrid-prometheus-exporter --crossbar ws://127.0.0.1:20408/ws  # wamp
```

## Development

`make test` and `make type-check` loop over both backend variants, syncing
each in turn (see the Makefile) — a single whole-tree `uv run pytest` won't
work for the same reason a single `uv sync` won't.

```sh
make test
make type-check
```

Build all package artifacts:

```sh
uv build --all-packages
```
