"""Tests for CLI drift summary helper."""
from tengil.cli_drift_helpers import analyze_drift
from tengil.core.drift_engine import (
    DriftItem,
    DriftReport,
    DriftSeverity,
    summarize_drift_report,
)


def test_summarize_drift_counts_and_samples():
    report = DriftReport()
    report.add(
        DriftItem(
            resource_type="dataset",
            identifier="tank/media",
            field="zfs.compression",
            desired="zstd",
            reality="lz4",
            severity=DriftSeverity.AUTO_MERGE,
            message="Compression mismatch",
        )
    )
    report.add(
        DriftItem(
            resource_type="container",
            identifier="restic",
            field="exists",
            desired=True,
            reality=False,
            severity=DriftSeverity.DANGEROUS,
            message="Container missing",
        )
    )
    report.add(
        DriftItem(
            resource_type="dataset",
            identifier="tank/backups",
            field="mountpoint",
            desired="/tank/backups",
            reality="/rpool/backups",
            severity=DriftSeverity.INFO,
            message="Mountpoint differs",
        )
    )

    summary = summarize_drift_report(report, limit=2)
    assert summary["counts"][DriftSeverity.AUTO_MERGE] == 1
    assert summary["counts"][DriftSeverity.DANGEROUS] == 1
    assert summary["counts"][DriftSeverity.INFO] == 1
    assert len(summary["samples"]) == 2
    assert summary["samples"][0]["resource"] == "dataset:tank/media"
    assert summary["samples"][1]["severity"] == DriftSeverity.DANGEROUS


class DummyLoader:
    def __init__(self, desired_state):
        self._desired = desired_state

    def build_desired_state(self):
        return self._desired


class DummyStateStore:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    def get_last_reality_snapshot(self):
        return self._snapshot


def test_analyze_drift_handles_missing_snapshot():
    loader = DummyLoader({"datasets": {}, "containers": {}})
    report, status = analyze_drift(loader, state_store=DummyStateStore(None))
    assert report is None
    assert status == "missing-snapshot"


def test_analyze_drift_returns_report_when_snapshot_exists():
    desired = {
        "datasets": {"tank/media": {"pool": "tank", "path": "tank/media", "properties": {"compression": "zstd"}}},
        "containers": {
            "jellyfin": {"name": "jellyfin", "mounts": [{"dataset": "tank/media", "mount": "/media"}], "profiles": []}
        },
    }
    reality = {
        "containers": [{"name": "jellyfin", "mounts": [{"mp": "/media"}]}],
        "zfs": {"datasets": {"tank": {"tank/media": {"compression": "lz4"}}}},
    }

    loader = DummyLoader(desired)
    store = DummyStateStore(reality)
    report, status = analyze_drift(loader, state_store=store)

    assert status is None
    assert report is not None
    assert not report.is_clean()
