"""Tests for the DriftEngine."""
from tengil.core.drift_engine import DriftEngine, DriftSeverity


def build_desired():
    return {
        "datasets": {
            "tank/media": {
                "pool": "tank",
                "path": "tank/media",
                "mountpoint": "/tank/media",
                "properties": {"compression": "zstd"},
                "containers": [
                    {"name": "jellyfin", "mount": "/media"}
                ],
            },
            "tank/backups": {
                "pool": "tank",
                "path": "tank/backups",
                "properties": {"compression": "lz4"},
                "containers": [],
            },
        },
        "containers": {
            "jellyfin": {
                "name": "jellyfin",
                "mounts": [{"dataset": "tank/media", "mount": "/media"}],
                "profiles": ["media"],
            },
            "restic": {
                "name": "restic",
                "mounts": [{"dataset": "tank/backups", "mount": "/data"}],
                "profiles": ["backups"],
            },
        },
    }


def build_reality():
    return {
        "containers": [
            {
                "name": "jellyfin",
                "mounts": [{"mp": "/media"}],
            }
        ],
        "zfs": {
            "datasets": {
                "tank": {
                    "tank/media": {"compression": "lz4", "mountpoint": "/tank/media"},
                }
            }
        },
    }


def test_detects_missing_dataset_and_container():
    engine = DriftEngine(build_desired(), build_reality())
    report = engine.run()

    assert len(report.items) == 3

    severities = {item.field: item.severity for item in report.items}
    assert severities["exists"] == DriftSeverity.DANGEROUS  # missing dataset
    assert any(item.field == "zfs.compression" for item in report.items)
    assert any(item.identifier == "restic" and item.field == "exists" for item in report.items)


def test_detects_container_mount_drift():
    desired = build_desired()
    desired["containers"]["jellyfin"]["mounts"][0]["mount"] = "/media/movies"

    engine = DriftEngine(desired, build_reality())
    report = engine.run()

    assert any(
        item.identifier == "jellyfin" and item.field == "mounts"
        for item in report.items
    )
