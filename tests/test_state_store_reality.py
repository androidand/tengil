"""Tests for StateStore reality snapshot helpers."""
import json
from pathlib import Path

from tengil.core.state_store import StateStore


def test_record_reality_snapshot_creates_file(tmp_path):
    state_file = tmp_path / ".tengil" / "state.json"
    store = StateStore(state_file=state_file)

    snapshot = {
        "metadata": {
            "generated_at": "2025-11-18T10:00:00Z",
            "mock": True,
        },
        "containers": [{"vmid": 100}],
        "storage": {},
        "zfs": {"datasets": {"tank": {"tank/data": {"used": "1G"}}}},
    }

    path = store.record_reality_snapshot(snapshot, keep_last=2)
    assert path is not None
    assert Path(path).exists()

    disk_payload = json.loads(Path(path).read_text())
    assert disk_payload["metadata"]["mock"] is True

    # State metadata persists summary + path
    state_data = json.loads(state_file.read_text())
    entry = state_data["reality"]["snapshots"][-1]
    assert entry["summary"]["containers"] == 1
    assert Path(entry["path"]).samefile(path)

    # Accessor loads snapshot from file if needed
    loaded = store.get_last_reality_snapshot()
    assert loaded["metadata"]["mock"]
