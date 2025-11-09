"""System hardware and ZFS pool scanner."""
import subprocess
import json
from typing import List, Tuple

from tengil.models.disk import DiskType, PhysicalDisk
from tengil.models.pool import ZFSPool


class SystemDiscovery:
    """Discover system disks and ZFS pools."""

    def __init__(self, mock: bool = False):
        self.mock = mock

    def discover_disks(self) -> List[PhysicalDisk]:
        """Discover all physical disks in the system."""
        if self.mock:
            return self._mock_disks()

        disks = []

        try:
            # Use lsblk to get disk info
            result = subprocess.run(
                ['lsblk', '-J', '-b', '-d', '-o', 'NAME,SIZE,TYPE,ROTA,MODEL'],
                capture_output=True, text=True, check=True
            )

            data = json.loads(result.stdout)

            for device in data.get('blockdevices', []):
                if device.get('type') != 'disk':
                    continue

                name = device['name']
                disk_type = self._detect_disk_type(name, device.get('rota', 1))

                disks.append(PhysicalDisk(
                    device=f"/dev/{name}",
                    size_bytes=int(device.get('size', 0)),
                    disk_type=disk_type,
                    model=device.get('model', 'Unknown').strip(),
                    serial=self._get_disk_serial(name),
                    rotational=device.get('rota', 1) == 1
                ))

        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
            # lsblk not available or failed
            pass

        return disks

    def discover_pools(self) -> List[ZFSPool]:
        """Discover existing ZFS pools."""
        if self.mock:
            return self._mock_pools()

        pools = []

        try:
            result = subprocess.run(
                ['zpool', 'list', '-H', '-p', '-o', 'name,size,alloc,free,health'],
                capture_output=True, text=True, check=True
            )

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                parts = line.split('\t')
                if len(parts) >= 5:
                    name = parts[0]

                    # Get pool config (devices and type)
                    devices, pool_type = self._get_pool_config(name)

                    pools.append(ZFSPool(
                        name=name,
                        size_bytes=int(parts[1]),
                        used_bytes=int(parts[2]),
                        available_bytes=int(parts[3]),
                        health=parts[4],
                        devices=devices,
                        pool_type=pool_type
                    ))

        except (subprocess.CalledProcessError, FileNotFoundError):
            # zpool not available
            pass

        return pools

    def _detect_disk_type(self, name: str, rotational: int) -> DiskType:
        """Detect disk type from device name and rotation."""
        if name.startswith('nvme'):
            return DiskType.NVME
        elif rotational == 0:
            return DiskType.SSD
        elif rotational == 1:
            return DiskType.HDD
        return DiskType.UNKNOWN

    def _get_disk_serial(self, name: str) -> str:
        """Get disk serial number."""
        try:
            result = subprocess.run(
                ['lsblk', '-n', '-o', 'SERIAL', f"/dev/{name}"],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip() or "unknown"
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    def _get_pool_config(self, pool_name: str) -> Tuple[List[str], str]:
        """Get pool device list and configuration type."""
        devices = []
        pool_type = "single"

        try:
            result = subprocess.run(
                ['zpool', 'status', pool_name],
                capture_output=True, text=True, check=True
            )

            lines = result.stdout.split('\n')
            in_config = False

            for line in lines:
                line = line.strip()

                if 'config:' in line.lower():
                    in_config = True
                    continue

                if in_config:
                    if line.startswith('errors:'):
                        break

                    # Parse config lines
                    if 'mirror' in line.lower():
                        pool_type = "mirror"
                    elif 'raidz1' in line.lower():
                        pool_type = "raidz1"
                    elif 'raidz2' in line.lower():
                        pool_type = "raidz2"
                    elif 'raidz3' in line.lower():
                        pool_type = "raidz3"

                    # Extract device paths
                    parts = line.split()
                    if parts and parts[0].startswith('/dev/'):
                        devices.append(parts[0])

        except subprocess.CalledProcessError:
            pass

        return devices, pool_type

    def _mock_disks(self) -> List[PhysicalDisk]:
        """Mock disk data for testing."""
        return [
            PhysicalDisk(
                device="/dev/nvme0n1",
                size_bytes=4_000_000_000_000,  # 4TB
                disk_type=DiskType.NVME,
                model="Samsung 990 PRO",
                serial="S123456",
                rotational=False
            ),
            PhysicalDisk(
                device="/dev/sda",
                size_bytes=10_000_000_000_000,  # 10TB
                disk_type=DiskType.HDD,
                model="WD Red Plus",
                serial="WD123",
                rotational=True
            ),
            PhysicalDisk(
                device="/dev/sdb",
                size_bytes=10_000_000_000_000,  # 10TB
                disk_type=DiskType.HDD,
                model="WD Red Plus",
                serial="WD124",
                rotational=True
            ),
        ]

    def _mock_pools(self) -> List[ZFSPool]:
        """Mock pool data for testing."""
        return [
            ZFSPool(
                name="rpool",
                size_bytes=4_000_000_000_000,
                used_bytes=500_000_000_000,
                available_bytes=3_500_000_000_000,
                health="ONLINE",
                devices=["/dev/nvme0n1"],
                pool_type="single",
                mock=True
            ),
            ZFSPool(
                name="tank",
                size_bytes=10_000_000_000_000,
                used_bytes=1_000_000_000_000,
                available_bytes=9_000_000_000_000,
                health="ONLINE",
                devices=["/dev/sda", "/dev/sdb"],
                pool_type="mirror",
                mock=True
            ),
        ]
