"""Helpers for resolving container targets referenced from the CLI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional, Tuple

from tengil.cli_support import find_config, is_mock
from tengil.config.loader import ConfigLoader
from tengil.services.proxmox.containers.discovery import ContainerDiscovery


@dataclass
class ContainerResolution:
    """Resolved container metadata."""

    vmid: int
    name: str


class ContainerResolutionError(RuntimeError):
    """Raised when a container target cannot be resolved."""


def resolve_container_target(
    target: str,
    config_path: Optional[str] = None,
) -> ContainerResolution:
    """Resolve a target expression to a VMID and container name."""
    if not target:
        raise ContainerResolutionError("Container target is required")

    target = target.strip()
    if not target:
        raise ContainerResolutionError("Container target is required")

    if target.isdigit():
        return ContainerResolution(vmid=int(target), name=str(target))

    dataset_hint: Optional[str] = None
    container_name: str = target

    if ":" in target:
        dataset_hint, container_name = _split_dataset_target(target)

    vmid: Optional[int] = None

    if dataset_hint:
        vmid = _resolve_from_config(dataset_hint, container_name, config_path)

    if vmid is None:
        vmid = _resolve_from_discovery(container_name)

    if vmid is None:
        raise ContainerResolutionError(
            f"Unable to resolve container '{target}'. Provide a VMID or update config."
        )

    return ContainerResolution(vmid=int(vmid), name=container_name)


def _split_dataset_target(target: str) -> Tuple[str, str]:
    dataset_part, container_part = target.split(":", 1)
    dataset_part = dataset_part.strip()
    container_part = container_part.strip()

    if not dataset_part or not container_part:
        raise ContainerResolutionError(
            f"Invalid dataset target: '{target}'. Expected format <pool/dataset>:<container>."
        )
    return dataset_part, container_part


def _resolve_from_config(
    dataset_hint: str,
    container_name: str,
    config_path: Optional[str],
) -> Optional[int]:
    config_file = find_config(config_path)
    loader = ConfigLoader(config_file)
    config = loader.load()

    pools = config.get("pools", {})
    pool_name, _, dataset_path = dataset_hint.partition("/")
    if not pool_name or not dataset_path:
        raise ContainerResolutionError(
            f"Invalid dataset hint '{dataset_hint}'. Use pool/dataset format."
        )

    pool_config = pools.get(pool_name)
    if not pool_config:
        raise ContainerResolutionError(
            f"Pool '{pool_name}' not found in config '{config_file}'."
        )

    dataset_config = _find_dataset_config(dataset_path, pool_config.get("datasets", {}))
    if not dataset_config:
        raise ContainerResolutionError(
            f"Dataset '{dataset_path}' not defined in pool '{pool_name}'."
        )

    container_entries = dataset_config.get("containers", [])
    for entry in container_entries:
        parsed = _parse_container_entry(entry)
        if parsed and parsed.name == container_name:
            return parsed.vmid

    return None


def _find_dataset_config(dataset_path: str, datasets: dict) -> Optional[dict]:
    if dataset_path in datasets:
        return datasets[dataset_path]

    # Normalize nested dataset keys when user refers to absolute dataset path.
    normalized = dataset_path.strip("/")
    for key, value in datasets.items():
        if key.strip("/") == normalized:
            return value
    return None


@dataclass
class _ContainerEntry:
    name: str
    vmid: Optional[int]


def _parse_container_entry(entry: Any) -> Optional[_ContainerEntry]:
    if isinstance(entry, str):
        parts = entry.split(":", 1)
        name = parts[0].strip()
        if not name:
            return None
        return _ContainerEntry(name=name, vmid=None)

    if isinstance(entry, dict):
        name = (entry.get("name") or entry.get("hostname") or "").strip()
        if not name:
            return None
        vmid = entry.get("vmid")
        if isinstance(vmid, str) and vmid.isdigit():
            vmid = int(vmid)
        return _ContainerEntry(name=name, vmid=vmid)

    return None


def _resolve_from_discovery(container_name: str) -> Optional[int]:
    discovery = ContainerDiscovery(mock=is_mock())
    vmid = discovery.find_container_by_name(container_name)
    if vmid is not None:
        return vmid

    for info in _safe_iter(discovery.list_containers()):
        if info.get("name") == container_name and "vmid" in info:
            try:
                return int(info["vmid"])
            except (TypeError, ValueError):
                continue
    return None


def _safe_iter(items: Iterable[Any]) -> Iterable[Any]:
    for item in items or []:
        yield item
