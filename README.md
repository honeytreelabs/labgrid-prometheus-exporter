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

## Metrics

Metrics are grouped into tiers, roughly ordered by value versus implementation
cost. All three tiers are implemented.

- **Tier 1 — utilization and self-health** (implemented):
  `labgrid_place_acquired`, `labgrid_place_changed_timestamp_seconds`,
  `labgrid_place_acquired_seconds`, `labgrid_places_acquired_by_user`,
  `labgrid_place_tag_info`, `labgrid_coordinator_connected`,
  `labgrid_places_last_update_timestamp_seconds`. Derived entirely from data
  `Place` already carries, plus the backend's own connection liveness — no
  further coordinator calls needed. `update_from_places()` diffs each poll
  against the previous one and removes series for places, tags, and users
  that dropped out, so released places, edited tags, or deleted places don't
  linger as stale metrics. This matters most for tags: they're commonly used
  to gate which places CI may use, so a removed or changed tag needs to
  actually disappear from `labgrid_place_tag_info`, not linger and keep a
  detagged place looking eligible.
- **Tier 2 — turnover** (implemented): `labgrid_place_acquire_total` /
  `labgrid_place_release_total` counters, tracking acquire/release
  transitions over time rather than just current state — Tier 1's gauges
  only answer "what's true right now," not "is this place churning
  constantly or basically idle." Reuses the same previous-vs-current
  diffing Tier 1 already does (`_previous_acquired_places`). A place
  deleted while acquired is not counted as a release — that's a removal,
  not a release, and conflating them would misrepresent actual usage
  turnover. Unlike the Tier 1 gauges, these counters are *not* removed
  when a place is deleted: they represent historical totals rather than
  current state, and clearing them would fabricate a counter reset
  unrelated to an actual process restart. Same poll-interval granularity
  caveat as everywhere else: an acquire/release cycle faster than the poll
  interval is invisible to these counters too.
- **Tier 3 — resource and reservation detail** (implemented):
  `labgrid_resource_available` (per-resource, labeled by exporter/group/name/cls)
  and reservation queue depth (`labgrid_reservations_pending`,
  `labgrid_reservation_wait_seconds`). Resources behave like Tier 1's
  gauges — labgrid already pushes resource updates the same way it does
  place updates, so `CoordinatorBackend.resources()` is a cheap sync read
  with the same diff-based cleanup as everywhere else (removed on
  disappearance; a resource's `cls` changing is treated as its old
  identity disappearing and a new one appearing, same as a tag's value
  changing). Reservations are genuinely different: labgrid never pushes
  reservation updates on either transport, so
  `CoordinatorBackend.reservations()` makes a real coordinator call every
  poll — the one async read-method in an otherwise-sync
  `CoordinatorBackend`, and the one metric update in `_poll()` wrapped in
  its own try/except, so a failed reservations fetch can't block
  place/resource metrics from updating that cycle. Reservation series
  are unlabeled (a reservation's token is randomly generated per request
  and unsuitable as a label), and `labgrid_reservation_wait_seconds`
  reports `0` rather than being absent when nothing is pending, since
  unlabeled gauges have no absence concept to begin with. Resource
  availability has real integration coverage too, against a real
  `labgrid-exporter` process (the `labgrid-exporter` service in
  `docker-compose.grpc.yml`/`docker-compose.wamp.yml`, distinct from the
  `exporter` service, which is our own exporter under test) — no `dut`
  container needed: the fixture resource is a plain `NetworkService`,
  which labgrid reports available without ever checking real connectivity
  (see `tests/integration/fixtures/exporter.yaml`).

## Reconnection

Neither labgrid transport's `ClientSession` reconnects on its own once its
connection to the coordinator drops (a coordinator restart during a
deployment, a network blip, ...) — that's expected for labgrid's own
tooling, which is one-shot and short-lived, but not acceptable for an
exporter meant to run unattended for a long time. So the exporter's poll
loop detects the drop itself and retries `connect()` on its own regular
poll interval — no separate backoff schedule, no manual restart needed.

Two things follow operationally: `labgrid_coordinator_connected` drops to
`0` for the duration of an outage, so alert on that (and on
`labgrid_places_last_update_timestamp_seconds` going stale) rather than
assuming metrics are always fresh. And place-level metrics
(`labgrid_place_acquired`, `labgrid_place_tag_info`, ...) intentionally
keep reporting their last-known values throughout the outage instead of
being cleared — a brief disconnect isn't the same as those places actually
being released or untagged, and clearing them would be actively misleading
to anything (dashboards, CI gating) reading those metrics.

## Development

`make test` and `make type-check` loop over both backend variants, syncing
each in turn (see the Makefile) — a single whole-tree `uv run pytest` won't
work for the same reason a single `uv sync` won't.

```sh
make test
make type-check
```

### Integration tests

`make test-integration` builds and runs a real labgrid coordinator (from
labgrid's own `dockerfiles/`, pinned to the exact tag each backend is tested
against — not pulled from a registry) plus a real
`labgrid-prometheus-exporter` container via Docker Compose
(`docker-compose.grpc.yml` / `docker-compose.wamp.yml`), then drives it with
`labgrid-client` and scrapes `/metrics` for real
(`tests/integration/`). It's slow and needs Docker, so unlike `make test`
it's **not** run by the pre-commit hook or on every commit — run it
explicitly, or from CI on a schedule/PR.

```sh
make test-integration
```

Build all package artifacts:

```sh
uv build --all-packages
```
