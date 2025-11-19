"""CLI integration tests for the `tg scan` command."""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tengil.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_mode(monkeypatch):
    monkeypatch.setenv("TG_MOCK", "1")
    yield
    monkeypatch.delenv("TG_MOCK", raising=False)


def test_scan_writes_reality_snapshot(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output_path = tmp_path / "reality.json"

    result = runner.invoke(app, ["scan", "--output", str(output_path), "--pretty", "--no-save-state"])

    assert result.exit_code == 0
    assert output_path.exists()

    payload = json.loads(output_path.read_text())
    assert payload["metadata"]["mock"] is True
    assert len(payload["containers"]) == 2
    assert "local-zfs" in payload["storage"]
    assert "datasets" in payload["zfs"]
    assert "Reality snapshot" in result.stdout


def test_scan_with_pool_filter(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output_path = tmp_path / "reality_tank.json"

    result = runner.invoke(app, ["scan", "--pool", "tank", "--output", str(output_path), "--no-save-state"])

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text())

    pools = list(payload["zfs"]["datasets"].keys())
    assert pools == ["tank"]


def test_scan_persists_state_snapshot(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["scan"])

    assert result.exit_code == 0

    state_file = Path(".tengil/state.json")
    assert state_file.exists()

    data = json.loads(state_file.read_text())
    snapshots = data["reality"]["snapshots"]
    assert snapshots

    latest = snapshots[-1]
    assert latest["summary"]["containers"] == 2
    assert latest["metadata"]["mock"] is True
    assert "path" in latest

    snapshot_path = Path(latest["path"])
    assert snapshot_path.exists()
    snapshot_payload = json.loads(snapshot_path.read_text())
    assert snapshot_payload["metadata"]["mock"] is True
