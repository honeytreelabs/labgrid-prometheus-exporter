# labgrid-prometheus-exporter-backend-grpc

`CoordinatorBackend` implementation for talking to a labgrid coordinator
over gRPC (labgrid releases 25.0 and later). Wraps labgrid's own
`labgrid.remote.client.ClientSession` rather than reimplementing the
protocol, since exactly one labgrid version is expected to be installed
alongside this package.

This is a library, not something end users install directly — install
`labgrid-prometheus-exporter[grpc]` instead, which pulls this package in and
provides the `labgrid-prometheus-exporter` command.

`plugin.py` exposes `add_arguments`/`create_backend`, the shape the
`labgrid-prometheus-exporter` meta package uses to discover and wire up
whichever backend is installed. A future `labgrid-prometheus-exporter-backend-wamp`
package would expose the same shape for labgrid releases up to 24.x (its
WAMP-based protocol), implementing the same
`labgrid_prometheus_exporter_core.interface.CoordinatorBackend` contract.
