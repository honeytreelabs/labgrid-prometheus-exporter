# AGENTS.md

Agent-facing operational notes for this labgrid toolkit repository. For what
the project does and how a human installs/uses it, read `README.md` first --
this file is about how to work *in* the repo without breaking things that
aren't obvious from the code alone.

## The one constraint that shapes everything here

`packages/labgrid-toolkit-backend-grpc` (labgrid >= 25.0) and `packages/labgrid-toolkit-backend-wamp`
(labgrid < 25.0) require incompatible `labgrid` version ranges, and are
declared as conflicting workspace members (`[tool.uv] conflicts` in the
root `pyproject.toml`). Consequences:

- **A bare `uv sync` or `uv run` at the repo root fails.** It always needs
  `--package` flags naming exactly one backend. Every Makefile target
  already does this correctly — prefer `make <target>` over inventing your
  own `uv` invocation.
- **There is no single synced environment containing both backends.**
  Whole-tree `pytest`/`ty check` invocations don't work; that's why `test`
  and `type-check` in the Makefile loop over both variants, re-syncing
  between them.
- If you need to run something manually:
  ```sh
  uv sync --package labgrid-toolkit-core \
          --package labgrid-prometheus-exporter \
          --package labgrid-toolkit-backend-grpc  # or -backend-wamp
  ```

## Commands

```sh
make test               # unit tests, both variants, fast, no Docker
make type-check          # ty, both variants
make lint / format / format-check    # ruff, whole tree, no variant looping needed
make test-integration    # Docker Compose + a real coordinator, both variants, slow
make build                # uv build --all-packages
```

`make test-integration` is **not** run by the pre-commit hook or `make
test` — it needs Docker and takes 1-2 minutes. Don't add it to either; run
it explicitly when touching backend connection logic.

## Repo map

- `packages/labgrid-toolkit-core` — transport-agnostic: Prometheus metric definitions
  (`metrics.py`), the poll/reconnect loop (`exporter.py`), and the
  `CoordinatorBackend`/`Place` contract (`interface.py`). No dependency on
  `labgrid`.
- `packages/labgrid-toolkit-backend-grpc`, `packages/labgrid-toolkit-backend-wamp` — one `CoordinatorBackend`
  implementation each, wrapping labgrid's own `ClientSession` rather than
  reimplementing the protocol. Pure libraries, no console script.
- `apps/prometheus-exporter` — the actual `labgrid-prometheus-exporter` console
  script. Discovers which single backend is installed at runtime
  (`labgrid_prometheus_exporter/backends.py`) and fails loudly if it's zero
  or more than one.
- `apps/prometheus-exporter/integration/tests/` — Docker Compose based end-to-end tests. Each stack
  has three real containers: `coordinator`, `prometheus-exporter` (this
  project's own exporter, the system under test), and `labgrid-exporter`
  (upstream labgrid's own exporter, registering a fixture resource so
  `labgrid_resource_available` has something real to report on). See
  "Naming" below for why those two are never both called just "exporter."
  `conftest.py` has the fixtures; `apps/prometheus-exporter/docker/compose.grpc.yml`/
  `apps/prometheus-exporter/docker/compose.wamp.yml` define the stacks.
- Root `conftest.py` — not a test file, a workaround (see below). Don't
  delete it because it looks unused.

## Naming: two different things are called "exporter"

This project (`labgrid-prometheus-exporter`) is a Prometheus exporter.
Separately, labgrid itself ships its own `labgrid-exporter` binary, which
registers hardware resources with the coordinator — a real one runs as the
`apps/prometheus-exporter/integration/tests/` fixture. These are unrelated processes that happen to
share a generic name. To avoid the ambiguity, say "Prometheus exporter"
(this project) or "labgrid exporter" (upstream) instead of bare
"exporter" wherever context doesn't already make it obvious, and prefer
identifiers that do the same: the `labgrid_exporter` label on
`labgrid_resource_available` (`packages/labgrid-toolkit-core/.../interface.py`'s
`Resource.labgrid_exporter`) and the `prometheus-exporter`/
`labgrid-exporter` Compose service names are both named this way
deliberately.

## Non-obvious gotchas (all found the hard way)

- **labgrid < 25.0 + Python >= 3.14 is broken at import time.**
  `labgrid.remote.client` runs `txaio.config.loop = asyncio.get_event_loop()`
  at module import time, which raises on Python >= 3.14 with no loop
  already set. The project targets Python 3.13 for compatibility with both
  supported labgrid generations. Worked around in two places: `-p no:labgrid` in pytest
  `addopts` (stops pytest autoloading labgrid's own pytest11 plugin) and
  the root `conftest.py` (sets an event loop before any test module can
  import `labgrid.remote.client` transitively). Both are still needed —
  they cover different import paths.
- **`ty` can't see through legacy `@attr.s`-style classes or dynamically
  set module attributes** (`labgrid.remote.client.ClientSession`,
  `txaio.config.loop`). Confirmed real/working at runtime, just invisible
  to static analysis. Suppressed with `# ty: ignore[...]` at the exact call
  site, with a comment — don't silence more broadly than that.
- **WAMP reconnection needed real fixes, not just labgrid wrapping.**
  `WampCoordinatorBackend.connect()` re-points `txaio.config.loop` at the
  actually-running loop (labgrid's own code pins it at import time, before
  `asyncio.run()` even creates the loop everything runs on — otherwise
  autobahn's internal timers, like WAMP ping/pong keepalive, silently never
  fire) and wraps the WAMP handshake wait in a timeout (labgrid's own
  `start_session()`, which this mirrors, has no timeout there — fine for a
  one-shot CLI a human Ctrl-C's, not fine for an unattended reconnect loop,
  which would otherwise wedge forever).
- **The gRPC/WAMP coordinator Docker images are built from labgrid's own
  source** (`dockerfiles/Dockerfile` in labgrid's repo, pinned to an exact
  tag via Compose's git-context build support), not pulled from a
  registry. The WAMP one needs a workaround baked into the compose
  command: labgrid's Dockerfile installs an unpinned `setuptools` at build
  time, and `setuptools >= 82` dropped `pkg_resources`, which crossbar
  still imports — see the `pip3 install 'setuptools<82'` step in
  `apps/prometheus-exporter/docker/compose.wamp.yml`.
- **Compose ports are ephemeral, not fixed**, and each compose file has an
  explicit `name:` — both deliberately, to avoid colliding with anything
  else already using 20408/9314 on the host, or with an unrelated Compose
  project sharing the directory-derived default name.
  `apps/prometheus-exporter/integration/tests/conftest.py` discovers the real published address via
  `docker compose port`, and does so **fresh on every `labgrid_client`
  call**, not once — a mid-test coordinator restart can otherwise leave a
  cached address stale.

## Reconnection

This Prometheus exporter's poll loop (`labgrid_toolkit_core/exporter.py`'s `_poll()`)
retries the coordinator connection on its own regular poll interval if it
drops — neither labgrid transport does this on its own. Upstream's own
`labgrid-exporter` binary doesn't either, and unlike this project it has
no fix for it: it just exits and relies on an external process supervisor
(systemd `Restart=`, a container orchestrator's restart policy, ...) to
start it again — see `restart_labgrid_exporter` in
`apps/prometheus-exporter/integration/tests/conftest.py` for where that bit this project's own
Docker Compose test fixture, since Compose's default is no restart. See the README's
"Reconnection" section for the operational implications (what
`labgrid_coordinator_connected` means, why place metrics hold their last
value through an outage instead of clearing). If you touch this logic,
`apps/prometheus-exporter/integration/tests/test_reconnect.py` actually restarts the coordinator
container mid-test to exercise it for real — run `make test-integration`,
don't rely on unit tests alone for reconnect changes.

## Git conventions

- Conventional Commits style: `type: lowercase summary` (`feat:`, `fix:`,
  `docs:`, ...), body explaining *why*, `git commit -s` for
  `Signed-off-by:`.
- **Never commit unless explicitly asked to.** "Generate a commit message"
  means generate the message, not run `git commit`.
- Prefer one focused commit per concern over one large commit — e.g. a
  Makefile fix and a feature change belong in separate commits even if
  discovered in the same session.
