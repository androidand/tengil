"""Physical disk models."""
from dataclasses import dataclass
from enum import Enum


class DiskType(Enum):
    """Disk technology type."""
    NVME = "nvme"
    SSD = "ssd"
    HDD = "hdd"
    UNKNOWN = "unknown"


@dataclass
class PhysicalDisk:
    """Represents a physical disk in the system."""
    device: str           # /dev/sda
    size_bytes: int       # Total size
    disk_type: DiskType   # NVME/SSD/HDD
    model: str            # Manufacturer model
    serial: str           # Serial number
    rotational: bool      # True for spinning disks

    @property
    def size_human(self) -> str:
        """Human-readable size."""
        size = self.size_bytes
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}PB"

    @property
    def is_fast(self) -> bool:
        """True if disk is fast (NVMe or SSD)."""
        return self.disk_type in (DiskType.NVME, DiskType.SSD)
