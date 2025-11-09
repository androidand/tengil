"""ZFS pool models."""
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import List


class PoolPurpose(Enum):
    """Intended use for a pool."""
    OS = "os"              # Operating system
    FAST = "fast"          # High-performance workloads
    BULK = "bulk"          # Mass storage
    BACKUP = "backup"      # Backup destination


@dataclass
class ZFSPool:
    """Represents an existing ZFS pool."""
    name: str
    size_bytes: int
    used_bytes: int
    available_bytes: int
    health: str           # ONLINE, DEGRADED, etc
    devices: List[str]    # Physical devices in pool
    pool_type: str        # mirror, raidz1, raidz2, etc
    mock: bool = False    # Mock mode for testing

    @property
    def is_os_pool(self) -> bool:
        """True if this looks like an OS pool (has ROOT dataset)."""
        if self.mock:
            # In mock mode, 'rpool' is the OS pool
            return self.name == "rpool"

        try:
            result = subprocess.run(
                ['zfs', 'list', '-H', '-o', 'name', '-t', 'filesystem'],
                capture_output=True, text=True, check=True
            )
            datasets = result.stdout.strip().split('\n')
            return f"{self.name}/ROOT" in datasets
        except subprocess.CalledProcessError:
            return False

    @property
    def purpose(self) -> PoolPurpose:
        """Infer the pool's purpose."""
        if self.is_os_pool:
            return PoolPurpose.OS

        # Check datasets for hints
        try:
            result = subprocess.run(
                ['zfs', 'list', '-H', '-o', 'name', '-r', self.name],
                capture_output=True, text=True, check=True
            )
            datasets = result.stdout.strip().split('\n')
            dataset_names = [d.lower() for d in datasets]

            # Media patterns suggest bulk storage
            media_patterns = ['media', 'movies', 'tv', 'music', 'photos']
            if any(pattern in ' '.join(dataset_names) for pattern in media_patterns):
                return PoolPurpose.BULK

            # Backup patterns
            backup_patterns = ['backup', 'backups', 'archive']
            if any(pattern in ' '.join(dataset_names) for pattern in backup_patterns):
                return PoolPurpose.BACKUP

        except subprocess.CalledProcessError:
            pass

        return PoolPurpose.FAST
