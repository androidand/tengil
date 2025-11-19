"""Reality model collector for Proxmox + ZFS."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from tengil.core.logger import get_logger
from tengil.core.zfs_manager import ZFSManager
from tengil.services.proxmox.manager import ProxmoxManager

logger = get_logger(__name__)

_BOOL_TRUE = {"1", "true", "yes", "on"}


class RealityStateCollector:
    """Collects the live state of Proxmox containers and ZFS datasets."""

    def __init__(
        self,
        mock: bool = False,
        proxmox_manager: Optional[ProxmoxManager] = None,
        zfs_manager: Optional[ZFSManager] = None,
    ) -> None:
        self.proxmox = proxmox_manager or ProxmoxManager(mock=mock)
        self.zfs = zfs_manager or ZFSManager(mock=mock)
        self.mock = bool(
            mock
            or getattr(self.proxmox, "mock", False)
            or getattr(self.zfs, "mock", False)
        )

    def collect(self, pools: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        """Collect the full reality snapshot."""
        containers = self._collect_containers()
        storage_cfg = self._collect_storage()
        datasets = self._collect_datasets(pools)

        metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mock": self.mock,
            "container_count": len(containers),
            "pool_count": len(datasets),
        }

        return {
            "metadata": metadata,
            "containers": containers,
            "storage": storage_cfg,
            "zfs": {"datasets": datasets},
        }

    # -------------------- Proxmox helpers --------------------

    def _collect_containers(self) -> List[Dict[str, Any]]:
        try:
            summaries = self.proxmox.list_containers() or []
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to list containers: %s", exc)
            return []

        result: List[Dict[str, Any]] = []
        for summary in summaries:
            vmid = self._coerce_int(summary.get("vmid"))
            if vmid is None:
                continue

            try:
                config = self.proxmox.get_container_config(vmid) or {}
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Failed to get config for vmid %s: %s", vmid, exc)
                config = {}

            mounts = self._collect_mounts(vmid, config)
            network = self._collect_network(config)
            features = self._collect_features(config)
            rootfs = self._collect_rootfs(config.get("rootfs"))

            container_state: Dict[str, Any] = {
                "vmid": vmid,
                "name": summary.get("name") or config.get("hostname"),
                "hostname": config.get("hostname"),
                "status": summary.get("status", "unknown"),
                "unprivileged": self._coerce_bool(config.get("unprivileged")),
                "resources": self._collect_resources(config),
                "rootfs": rootfs,
                "mounts": mounts,
                "network": network,
                "features": features,
                "raw_config": config,
            }

            # Drop None values for cleaner diffs
            result.append({k: v for k, v in container_state.items() if v is not None})

        return sorted(result, key=lambda item: item.get("vmid", 0))

    def _collect_resources(self, config: Dict[str, str]) -> Dict[str, Any]:
        resources = {
            "memory_mb": self._coerce_int(config.get("memory")),
            "swap_mb": self._coerce_int(config.get("swap")),
            "cores": self._coerce_int(config.get("cores")),
            "cpu_units": self._coerce_int(config.get("cpuunits")),
            "cpu_limit": self._coerce_float(config.get("cpulimit")),
        }
        return {k: v for k, v in resources.items() if v is not None}

    def _collect_rootfs(self, rootfs_value: Optional[str]) -> Optional[Dict[str, Any]]:
        if not rootfs_value:
            return None
        parsed = self._parse_device_config(rootfs_value, primary_key="volume")
        if "size" in parsed:
            parsed["size"] = parsed["size"]
        return parsed

    def _collect_mounts(self, vmid: int, config: Dict[str, str]) -> List[Dict[str, Any]]:
        mounts: Dict[str, Dict[str, Any]] = {}
        for key, value in config.items():
            if key.startswith("mp"):
                mount = self._parse_device_config(value, primary_key="volume")
                mount_id = key
                mount["id"] = mount_id
                mount["readonly"] = self._coerce_bool(mount.pop("ro", None))
                mounts[mount_id] = mount

        try:
            manager_mounts = self.proxmox.get_container_mounts(vmid) or {}
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to load mounts for vmid %s: %s", vmid, exc)
            manager_mounts = {}

        for mount_id, mount_info in manager_mounts.items():
            existing = mounts.get(mount_id, {}).copy()
            combined = {**mount_info, **existing}
            combined["id"] = mount_id
            combined["readonly"] = self._coerce_bool(
                existing.get("ro") or mount_info.get("ro")
            )
            mounts[mount_id] = combined

        ordered = [mounts[key] for key in sorted(mounts.keys())]
        return ordered

    def _collect_network(self, config: Dict[str, str]) -> List[Dict[str, Any]]:
        adapters: List[Dict[str, Any]] = []
        for key, value in config.items():
            if key.startswith("net"):
                adapter = self._parse_kv_pairs(value)
                adapter["id"] = key
                if "firewall" in adapter:
                    adapter["firewall"] = self._coerce_bool(adapter["firewall"])
                if "link_down" in adapter:
                    adapter["link_down"] = self._coerce_bool(adapter["link_down"])
                if "tag" in adapter:
                    tag = self._coerce_int(adapter["tag"])
                    adapter["tag"] = tag if tag is not None else adapter["tag"]
                adapters.append(adapter)
        return sorted(adapters, key=lambda item: item.get("id", ""))

    def _collect_features(self, config: Dict[str, str]) -> Dict[str, Any]:
        features: Dict[str, Any] = {}
        feature_string = config.get("features")
        if feature_string:
            for key, value in self._parse_kv_pairs(feature_string).items():
                features[key] = self._coerce_bool(value)

        for key in (
            "nesting",
            "keyctl",
            "fuse",
            "mount",
            "nfs",
            "cgroup2",
            "protection",
            "agent",
        ):
            if key in config:
                features[key] = self._coerce_bool(config[key])

        return features

    def _collect_storage(self) -> Dict[str, Any]:
        try:
            return self.proxmox.parse_storage_cfg() or {}
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to parse storage.cfg: %s", exc)
            return {}

    # -------------------- ZFS helpers --------------------

    def _collect_datasets(self, pools: Optional[Iterable[str]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        pool_list = list(pools) if pools else list(self._infer_pools())
        datasets: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for pool in pool_list:
            try:
                datasets[pool] = self.zfs.list_datasets(pool)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Failed to list datasets for %s: %s", pool, exc)
                datasets[pool] = {}
        return datasets

    def _infer_pools(self) -> List[str]:
        storage = self._collect_storage()
        pools = set()
        for cfg in storage.values():
            pool = cfg.get("pool")
            if pool:
                # Handle pool/dataset syntax (e.g. rpool/data -> rpool)
                root_pool = pool.split('/')[0]
                pools.add(root_pool)
        return sorted(pools)

    # -------------------- Parsing helpers --------------------

    def _parse_device_config(self, value: str, primary_key: str) -> Dict[str, Any]:
        parsed = self._parse_kv_pairs(value)
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if parts and "=" not in parts[0]:
            parsed.setdefault(primary_key, parts[0])
        if "ro" in parsed:
            parsed["ro"] = parsed["ro"]
        return parsed

    @staticmethod
    def _parse_kv_pairs(value: str) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                key, raw = part.split("=", 1)
                result[key.strip()] = raw.strip()
        return result

    @staticmethod
    def _coerce_bool(value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text == "0" or text in {"false", "no", "off"}:
            return False
        if text in _BOOL_TRUE:
            return True
        return None

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(str(value), 10)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None
