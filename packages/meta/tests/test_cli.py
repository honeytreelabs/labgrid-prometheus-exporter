"""cli.main() wires the discovered backend's arguments into the shared parser."""

from __future__ import annotations

import sys

import pytest
from labgrid_prometheus_exporter.cli import main


def test_main_reports_missing_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "labgrid_prometheus_exporter.backends._BACKENDS", {"fake": "no_such_module_at_all"}
    )
    monkeypatch.setattr(sys, "argv", ["labgrid-prometheus-exporter"])

    with pytest.raises(RuntimeError, match="No labgrid-prometheus-exporter backend"):
        main()
