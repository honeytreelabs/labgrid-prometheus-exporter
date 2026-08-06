# labgrid-prometheus-exporter-core

Shared logic for `labgrid-prometheus-exporter`: the Prometheus metric
definitions, the HTTP server wiring, and the `CoordinatorBackend` contract
that transport-specific backend packages implement.

This package has no dependency on `labgrid` itself and is not installed
directly by end users — install one of the `labgrid-prometheus-exporter-backend-*`
packages instead, matching the labgrid release your coordinator runs.
