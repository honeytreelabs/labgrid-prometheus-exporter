from labgrid_prometheus_exporter.cli import main


def test_main_prints_stub_message(capsys):
    assert main() == 0

    captured = capsys.readouterr()
    assert captured.out == "labgrid-prometheus-exporter stub\n"
    assert captured.err == ""
