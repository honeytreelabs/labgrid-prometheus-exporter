"""Work around a labgrid < 25.0 import-time bug, before any test module runs.

labgrid.remote.client (the WAMP-era client, used by backend-wamp) sets
`txaio.config.loop = asyncio.get_event_loop()` as a *module-level*
statement. On Python >= 3.14, asyncio.get_event_loop() raises RuntimeError
if no loop is set for the current thread -- the implicit "create one"
fallback pytest relied on was removed there. Unconditionally setting a loop
here, before pytest imports any test module that transitively imports
labgrid.remote.client, means get_event_loop() always finds one already set
and never takes that failing path, on any Python version. Harmless for
backend-grpc, which doesn't have this issue.
"""

import asyncio

asyncio.set_event_loop(asyncio.new_event_loop())
