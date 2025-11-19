"""Helpers to serialize Tengil configs into a normalized desired-state model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class DesiredStateBuilder:
    """Builds a normalized desired-state document from a processed config."""

    processed_config: Dict[str, Any]
    source_path: str

    def build(self) -> Dict[str, Any]:
        """Return a structured desired-state mapping."""
        pools = self.processed_config.get("pools", {})
        datasets: Dict[str, Any] = {}
        containers: Dict[str, Any] = {}

        for pool_name, pool_config in pools.items():
            for dataset_name, dataset_config in pool_config.get("datasets", {}).items():
                path = f"{pool_name}/{dataset_name}"
                dataset_entry = self._normalize_dataset(pool_name, dataset_name, dataset_config)
                datasets[path] = dataset_entry

                for container in dataset_entry["containers"]:
                    containers.setdefault(container["name"], {
                        "name": container["name"],
                        "mounts": [],
                        "profiles": set(),
                    })
                    containers[container["name"]]["mounts"].append({
                        "dataset": path,
                        "mount": container.get("mount"),
                        "permissions": container.get("permissions"),
                    })
                    profile = dataset_entry.get("profile")
                    if profile:
                        containers[container["name"]]["profiles"].add(profile)

        container_list = {
            name: {
                "name": data["name"],
                "mounts": data["mounts"],
                "profiles": sorted(data["profiles"]),
            }
            for name, data in containers.items()
        }

        metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": self.source_path,
            "pool_count": len(pools),
            "dataset_count": len(datasets),
            "container_count": len(container_list),
            "version": "1.0",
        }

        return {
            "metadata": metadata,
            "pools": {
                pool_name: {
                    "name": pool_name,
                    "datasets": sorted(
                        [
                            {
                                "name": dataset_name,
                                "path": f"{pool_name}/{dataset_name}",
                            }
                            for dataset_name in pool.get("datasets", {}).keys()
                        ],
                        key=lambda item: item["path"],
                    ),
                }
                for pool_name, pool in pools.items()
            },
            "datasets": datasets,
            "containers": container_list,
        }

    def _normalize_dataset(
        self,
        pool_name: str,
        dataset_name: str,
        dataset_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a deterministic dataset entry."""
        desired = {
            "name": dataset_name,
            "pool": pool_name,
            "path": f"{pool_name}/{dataset_name}",
            "profile": dataset_config.get("profile"),
            "mountpoint": dataset_config.get("mountpoint"),
            "shares": dataset_config.get("shares", {}),
            "containers": self._normalize_containers(dataset_config.get("containers")),
            "properties": dataset_config.get("zfs", {}),
            "metadata": {
                "auto_parent": dataset_config.get("_auto_parent", False),
            },
        }
        return desired

    @staticmethod
    def _normalize_containers(raw_containers: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Normalize the container list on a dataset."""
        if not raw_containers:
            return []
        result: List[Dict[str, Any]] = []
        for container in raw_containers:
            result.append({
                "name": container.get("name"),
                "mount": container.get("mount"),
                "permissions": container.get("permissions"),
                "options": container.get("options", {}),
            })
        return sorted(result, key=lambda entry: (entry.get("name") or "", entry.get("mount") or ""))


def build_desired_state(processed_config: Dict[str, Any], source_path: str) -> Dict[str, Any]:
    """Convenience wrapper returning the desired-state mapping."""
    builder = DesiredStateBuilder(processed_config=processed_config, source_path=source_path)
    return builder.build()
