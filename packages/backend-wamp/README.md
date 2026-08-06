# labgrid-prometheus-exporter-backend-wamp

`CoordinatorBackend` implementation for talking to a labgrid coordinator
over its WAMP/crossbar protocol (labgrid releases up to 24.x). Wraps
labgrid's own `labgrid.remote.client.ClientSession` (an autobahn
`ApplicationSession`) rather than reimplementing the protocol, mirroring
the same wrapping approach as `labgrid-prometheus-exporter-backend-grpc`.

This is a library, not something end users install directly — install
`labgrid-prometheus-exporter[wamp]` instead.
