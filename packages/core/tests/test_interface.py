"""A fake backend satisfies CoordinatorBackend without importing it.

Demonstrates that backend packages don't need to depend on -core to conform
to its contract: structural typing (typing.Protocol) is enough.
"""

from __future__ import annotations

from labgrid_prometheus_exporter_core.interface import CoordinatorBackend, Place


class FakeBackend:
    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    def places(self) -> dict[str, Place]:
        return {}

    def connected(self) -> bool:
        return True


def test_fake_backend_satisfies_protocol() -> None:
    assert isinstance(FakeBackend(), CoordinatorBackend)
