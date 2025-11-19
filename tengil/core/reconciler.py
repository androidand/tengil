"""Drift reconciliation helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from tengil.core.drift_engine import DriftReport, DriftSeverity


@dataclass
class ReconciliationPolicy:
    """User preference for reconciling drift."""

    prefer_gui: bool = False  # True = reality wins, False = desired wins
    auto_merge: bool = True   # Auto-merge harmless drift without confirmation


@dataclass
class ReconciliationPlan:
    """Organized sets of actions to reconcile drift."""

    apply_to_reality: List = field(default_factory=list)
    update_desired: List = field(default_factory=list)
    confirmations_required: List = field(default_factory=list)
    informational: List = field(default_factory=list)

    def requires_confirmation(self) -> bool:
        return bool(self.confirmations_required)


class ReconciliationEngine:
    """Convert a drift report into reconciliation actions."""

    def __init__(self, drift_report: DriftReport, policy: ReconciliationPolicy | None = None):
        self.report = drift_report
        self.policy = policy or ReconciliationPolicy()

    def build_plan(self) -> ReconciliationPlan:
        plan = ReconciliationPlan()

        for item in self.report.items:
            if item.severity == DriftSeverity.DANGEROUS:
                plan.confirmations_required.append(item)
                continue

            if item.severity == DriftSeverity.AUTO_MERGE:
                if self.policy.prefer_gui:
                    plan.update_desired.append(item)
                else:
                    plan.apply_to_reality.append(item)
                continue

            # Default to informational
            plan.informational.append(item)

        if not self.policy.auto_merge:
            # Downgrade auto-merge actions to confirmation when auto_merge disabled
            plan.confirmations_required.extend(plan.apply_to_reality)
            plan.confirmations_required.extend(plan.update_desired)
            plan.apply_to_reality = []
            plan.update_desired = []

        return plan
