"""Tests for the ReconciliationEngine."""
from tengil.core.drift_engine import DriftItem, DriftReport, DriftSeverity
from tengil.core.reconciler import ReconciliationEngine, ReconciliationPolicy


def sample_report():
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
    return report


def test_plan_prefers_desired_by_default():
    plan = ReconciliationEngine(sample_report()).build_plan()

    assert len(plan.apply_to_reality) == 1
    assert len(plan.update_desired) == 0
    assert len(plan.confirmations_required) == 1
    assert plan.requires_confirmation()


def test_plan_prefers_gui_when_policy_enabled():
    policy = ReconciliationPolicy(prefer_gui=True)
    plan = ReconciliationEngine(sample_report(), policy=policy).build_plan()

    assert len(plan.apply_to_reality) == 0
    assert len(plan.update_desired) == 1


def test_disabling_auto_merge_requires_confirmation():
    policy = ReconciliationPolicy(auto_merge=False)
    plan = ReconciliationEngine(sample_report(), policy=policy).build_plan()

    assert not plan.apply_to_reality
    assert not plan.update_desired
    assert len(plan.confirmations_required) == 2
