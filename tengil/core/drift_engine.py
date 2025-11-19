"""Desired vs. reality drift detection helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class DriftSeverity:
    """Severity levels used for drift classification."""

    INFO = "info"
    AUTO_MERGE = "auto-merge"
    DANGEROUS = "dangerous"


@dataclass
class DriftItem:
    """A single drift finding."""

    resource_type: str
    identifier: str
    field: str
    desired: Any
    reality: Any
    severity: str
    message: str
    context: Optional[Dict[str, Any]] = None


@dataclass
class DriftReport:
    """Aggregated drift report."""

    items: List[DriftItem] = field(default_factory=list)

    def add(self, item: DriftItem) -> None:
        self.items.append(item)

    def is_clean(self) -> bool:
        return not self.items

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for item in self.items:
            counts[item.severity] = counts.get(item.severity, 0) + 1
        return counts


class DriftEngine:
    """Compares desired vs. reality models to detect drift."""

    def __init__(self, desired_state: Dict[str, Any], reality_state: Dict[str, Any]):
        self.desired = desired_state or {}
        self.reality = reality_state or {}
        self.report = DriftReport()

    def run(self) -> DriftReport:
        self.report = DriftReport()
        self._compare_datasets()
        self._compare_containers()
        return self.report

    # ----------------------------
    # Dataset comparison helpers
    # ----------------------------

    def _compare_datasets(self) -> None:
        desired_datasets: Dict[str, Dict[str, Any]] = self.desired.get("datasets", {})
        reality_pools: Dict[str, Dict[str, Any]] = (
            self.reality.get("zfs", {}).get("datasets", {}) or {}
        )

        for path, dataset in desired_datasets.items():
            pool_name = dataset.get("pool")
            reality_dataset = self._get_reality_dataset(reality_pools, pool_name, path)
            if reality_dataset is None:
                self.report.add(
                    DriftItem(
                        resource_type="dataset",
                        identifier=path,
                        field="exists",
                        desired=True,
                        reality=False,
                        severity=DriftSeverity.DANGEROUS,
                        message=f"Dataset {path} missing on reality host",
                        context=dataset,
                    )
                )
                continue

            self._compare_dataset_props(path, dataset, reality_dataset)

    @staticmethod
    def _get_reality_dataset(
        reality_pools: Dict[str, Dict[str, Any]], pool_name: Optional[str], path: str
    ) -> Optional[Dict[str, Any]]:
        if pool_name is None:
            return None
        pool_state = reality_pools.get(pool_name)
        if not pool_state:
            return None
        return pool_state.get(path)

    def _compare_dataset_props(
        self,
        dataset_path: str,
        desired_dataset: Dict[str, Any],
        reality_dataset: Dict[str, Any],
    ) -> None:
        desired_props = desired_dataset.get("properties", {})
        mountpoint = desired_dataset.get("mountpoint")

        # Compare mountpoint if reality reports it
        reality_mount = reality_dataset.get("mountpoint")
        if mountpoint and reality_mount and mountpoint != reality_mount:
            self.report.add(
                DriftItem(
                    resource_type="dataset",
                    identifier=dataset_path,
                    field="mountpoint",
                    desired=mountpoint,
                    reality=reality_mount,
                    severity=DriftSeverity.AUTO_MERGE,
                    message=f"Mountpoint drift for {dataset_path}",
                )
            )

        for prop, desired_value in desired_props.items():
            reality_value = reality_dataset.get(prop)
            if reality_value is None:
                continue
            if str(desired_value) != str(reality_value):
                self.report.add(
                    DriftItem(
                        resource_type="dataset",
                        identifier=dataset_path,
                        field=f"zfs.{prop}",
                        desired=desired_value,
                        reality=reality_value,
                        severity=DriftSeverity.AUTO_MERGE,
                        message=f"ZFS property '{prop}' drift on {dataset_path}",
                    )
                )

    # ----------------------------
    # Container comparison helpers
    # ----------------------------

    def _compare_containers(self) -> None:
        desired_containers: Dict[str, Any] = self.desired.get("containers", {})
        reality_containers = {
            container.get("name"): container
            for container in self.reality.get("containers", [])
            if container.get("name")
        }

        for name, container_data in desired_containers.items():
            reality_container = reality_containers.get(name)
            if reality_container is None:
                self.report.add(
                    DriftItem(
                        resource_type="container",
                        identifier=name,
                        field="exists",
                        desired=True,
                        reality=False,
                        severity=DriftSeverity.DANGEROUS,
                        message=f"Container '{name}' missing in reality state",
                    )
                )
                continue

            self._compare_container_mounts(name, container_data, reality_container)

    def _compare_container_mounts(
        self,
        container_name: str,
        desired_container: Dict[str, Any],
        reality_container: Dict[str, Any],
    ) -> None:
        desired_mounts = desired_container.get("mounts", [])
        reality_mounts = reality_container.get("mounts", [])
        reality_mount_paths = {
            mount.get("mp") or mount.get("mountpoint")
            for mount in reality_mounts
            if mount
        }

        for desired_mount in desired_mounts:
            mount_path = desired_mount.get("mount")
            if not mount_path:
                continue
            if mount_path not in reality_mount_paths:
                self.report.add(
                    DriftItem(
                        resource_type="container",
                        identifier=container_name,
                        field="mounts",
                        desired=mount_path,
                        reality=list(sorted(filter(None, reality_mount_paths))),
                        severity=DriftSeverity.AUTO_MERGE,
                        message=f"Container '{container_name}' missing mount {mount_path}",
                    )
                )


def summarize_drift_report(report: DriftReport, limit: int = 5) -> Dict[str, List[Dict[str, str]]]:
    """Return summary counts and sample drift entries."""
    counts = report.summary()
    samples: List[Dict[str, str]] = []
    for item in report.items[:limit]:
        samples.append(
            {
                "severity": item.severity,
                "resource": f"{item.resource_type}:{item.identifier}",
                "field": item.field,
                "message": item.message,
            }
        )

    return {"counts": counts, "samples": samples}
