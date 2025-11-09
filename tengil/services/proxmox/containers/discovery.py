"""Container discovery and information retrieval."""
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class ContainerDiscovery:
    """Discovers and retrieves information about Proxmox LXC containers."""

    def __init__(self, mock: bool = False):
        self.mock = mock

    def list_containers(self) -> List[Dict]:
        """List all LXC containers.

        Returns:
            List of container dicts with vmid, name, status
        """
        if self.mock:
            logger.info("MOCK: Would list containers")
            return [
                {'vmid': 100, 'name': 'jellyfin', 'status': 'running'},
                {'vmid': 101, 'name': 'nextcloud', 'status': 'stopped'}
            ]

        containers = []
        try:
            # Use pct list to get all containers
            result = subprocess.run(
                ["pct", "list"],
                capture_output=True,
                text=True,
                check=True
            )

            # Parse output (skip header)
            for line in result.stdout.strip().split('\n')[1:]:
                if line:
                    parts = line.split()
                    if len(parts) >= 3:
                        containers.append({
                            'vmid': int(parts[0]),
                            'status': parts[1],
                            'name': parts[2] if len(parts) > 2 else ''
                        })

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list containers: {e}")

        return containers

    def find_container_by_name(self, name: str) -> Optional[int]:
        """Find container VMID by name.

        Args:
            name: Container hostname

        Returns:
            Container VMID or None if not found
        """
        containers = self.list_containers()
        for container in containers:
            if container.get('name') == name:
                return container['vmid']
        return None

    def get_container_config(self, vmid: int) -> Dict:
        """Get raw configuration for a specific container.

        Args:
            vmid: Container ID

        Returns:
            Dict of config key/value pairs
        """
        if self.mock:
            logger.info(f"MOCK: Would get config for container {vmid}")
            return {
                'hostname': 'jellyfin',
                'rootfs': 'local-lvm:vm-100-disk-0,size=8G',
                'mp0': '/tank/media,mp=/media'
            }

        config = {}
        config_path = Path(f"/etc/pve/lxc/{vmid}.conf")

        if not config_path.exists():
            logger.warning(f"Container config not found: {config_path}")
            return config

        try:
            with open(config_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            config[key.strip()] = value.strip()

        except Exception as e:
            logger.error(f"Failed to read container config: {e}")

        return config

    def get_container_info(self, vmid: int) -> Optional[Dict]:
        """Get detailed information about a container.

        Args:
            vmid: Container ID

        Returns:
            Dict with container details or None if not found:
            {
                'vmid': 100,
                'name': 'jellyfin',
                'status': 'running',
                'template': 'debian-12-standard',
                'memory': 2048,
                'cores': 2,
                'rootfs': 'local-lvm:vm-100-disk-0,size=8G',
                'mounts': {...}
            }
        """
        if self.mock:
            # Get status from list_containers for accurate mock data
            containers = self.list_containers()
            container_data = next((c for c in containers if c['vmid'] == vmid), None)
            if container_data:
                return {
                    'vmid': vmid,
                    'name': container_data['name'],
                    'status': container_data['status'],
                    'template': 'debian-12-standard',
                    'memory': 2048,
                    'cores': 2,
                    'rootfs': 'local-lvm:vm-100-disk-0,size=8G',
                    'mounts': {}
                }
            return None

        # Check if container exists
        if not self.container_exists(vmid):
            return None

        # Get basic info from pct list
        containers = self.list_containers()
        container_info = next((c for c in containers if c['vmid'] == vmid), None)

        if not container_info:
            return None

        # Get config details
        config = self.get_container_config(vmid)

        # Extract relevant fields
        info = {
            'vmid': vmid,
            'name': container_info.get('name', config.get('hostname', '')),
            'status': container_info.get('status', 'unknown'),
            'template': config.get('ostemplate', ''),
            'memory': int(config.get('memory', 512)),
            'cores': int(config.get('cores', 1)),
            'rootfs': config.get('rootfs', ''),
            'mounts': {}  # Will be populated by MountManager
        }

        return info

    def get_container_by_name(self, name: str) -> Optional[Dict]:
        """Get detailed container info by name.

        Convenience method that combines find_container_by_name and get_container_info.

        Args:
            name: Container hostname

        Returns:
            Container info dict or None
        """
        vmid = self.find_container_by_name(name)
        if vmid:
            return self.get_container_info(vmid)
        return None

    def get_all_containers_info(self) -> List[Dict]:
        """Get detailed info for all containers.

        Returns:
            List of container info dicts
        """
        containers = self.list_containers()
        result = []

        for container in containers:
            vmid = container['vmid']
            info = self.get_container_info(vmid)
            if info:
                result.append(info)

        return result

    def container_exists(self, vmid: int) -> bool:
        """Check if a container exists.

        Args:
            vmid: Container ID

        Returns:
            True if container exists
        """
        if self.mock:
            return True  # In mock mode, assume container exists

        try:
            cmd = ["pct", "status", str(vmid)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError:
            return False
