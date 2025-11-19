"""Resource validation for auto-created LXC containers."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


@dataclass
class HostResources:
    """Detected host capacity in MB/cores."""

    total_memory_mb: int
    total_swap_mb: int
    total_cores: int


@dataclass
class ResourceValidationResult:
    """Outcome of resource validation."""

    auto_create_count: int = 0
    total_memory_mb: int = 0
    total_cores: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def has_errors(self) -> bool:
        return bool(self.errors)


class ResourceValidator:
    """Validate resource usage for auto-created containers."""

    def __init__(self, config: Dict[str, dict], host: HostResources):
        self.config = config or {}
        self.host = host

    def validate(self) -> ResourceValidationResult:
        result = ResourceValidationResult()

        for container in self._iter_auto_create_containers():
            result.auto_create_count += 1
            resources = container.get("resources", {}) or {}

            memory = self._parse_memory(resources.get("memory"))
            cores = self._parse_int(resources.get("cores"), default=1)

            result.total_memory_mb += memory
            result.total_cores += cores

        if result.auto_create_count == 0:
            return result

        self._evaluate_memory(result)
        self._evaluate_cores(result)
        return result

    def _iter_auto_create_containers(self) -> Iterable[Dict]:
        pools = (self.config or {}).get("pools", {})
        for pool in pools.values():
            for dataset in (pool or {}).get("datasets", {}).values():
                for container in dataset.get("containers", []) or []:
                    if not isinstance(container, dict):
                        continue
                    if container.get("auto_create"):
                        yield container

    def _evaluate_memory(self, result: ResourceValidationResult) -> None:
        available = self.host.total_memory_mb
        requested = result.total_memory_mb
        if available <= 0:
            return

        usage_pct = requested / available
        if requested > available:
            result.errors.append(
                f"Auto-created containers request {requested} MB RAM but host has {available} MB"
            )
        elif usage_pct >= 0.9:
            result.warnings.append(
                f"Auto-created containers will consume {usage_pct:.0%} of host RAM ({requested}/{available} MB)"
            )

    def _evaluate_cores(self, result: ResourceValidationResult) -> None:
        available = max(self.host.total_cores, 1)
        requested = result.total_cores
        usage_pct = requested / available

        if requested > available:
            result.errors.append(
                f"Auto-created containers request {requested} CPU cores but host reports {available}"
            )
        elif usage_pct >= 0.9:
            result.warnings.append(
                f"Auto-created containers will consume {usage_pct:.0%} of available CPU cores ({requested}/{available})"
            )

    @staticmethod
    def _parse_memory(value: Optional[object], default: int = 512) -> int:
        """Return memory in MB."""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            text = value.strip().upper()
            multiplier = 1
            if text.endswith("G"):
                multiplier = 1024
                text = text[:-1]
            elif text.endswith("M"):
                multiplier = 1
                text = text[:-1]
            try:
                return int(float(text) * multiplier)
            except ValueError:
                return default
        return default

    @staticmethod
    def _parse_int(value: Optional[object], default: int = 1) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


def detect_host_resources() -> HostResources:
    """Detect host capacity using psutil or /proc/meminfo fallback."""
    total_mem = _detect_memory_from_psutil()
    total_swap = None
    total_cores = os.cpu_count() or 1

    if total_mem is None:
        total_mem, total_swap = _detect_memory_from_proc()

    if total_swap is None:
        total_swap = _detect_swap_from_psutil()

    return HostResources(
        total_memory_mb=total_mem or 0,
        total_swap_mb=total_swap or 0,
        total_cores=total_cores,
    )


def _detect_memory_from_psutil() -> Optional[int]:
    try:
        import psutil  # type: ignore

        return int(psutil.virtual_memory().total // (1024 * 1024))
    except Exception:
        return None


def _detect_swap_from_psutil() -> Optional[int]:
    try:
        import psutil  # type: ignore

        return int(psutil.swap_memory().total // (1024 * 1024))
    except Exception:
        return None


def _detect_memory_from_proc() -> tuple[Optional[int], Optional[int]]:
    meminfo = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                meminfo[key.strip()] = value.strip()
    except FileNotFoundError:
        return None, None

    total_mem = _meminfo_to_mb(meminfo.get("MemTotal"))
    total_swap = _meminfo_to_mb(meminfo.get("SwapTotal"))
    return total_mem, total_swap


def _meminfo_to_mb(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    parts = value.split()
    try:
        kilobytes = float(parts[0])
        return int(kilobytes / 1024)
    except (ValueError, IndexError):
        return None
