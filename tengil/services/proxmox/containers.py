"""Proxmox container mount management."""
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class ContainerManager:
    """Manages Proxmox LXC container mounts."""

    def __init__(self, mock: bool = False):
        self.mock = mock

    def list_containers(self) -> List[Dict]:
        """List all LXC containers."""
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

    def get_container_config(self, vmid: int) -> Dict:
        """Get configuration for a specific container."""
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

    def container_exists(self, vmid: int) -> bool:
        """Check if a container exists."""
        if self.mock:
            return True  # In mock mode, assume container exists

        try:
            cmd = ["pct", "status", str(vmid)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def get_container_mounts(self, vmid: int) -> Dict[str, Dict[str, str]]:
        """Get all mount points configured for a container.

        Returns:
            Dict of mount point IDs to their configuration
            Example: {
                'mp0': {'volume': '/tank/movies', 'mp': '/movies', 'ro': '0'},
                'mp1': {'volume': '/tank/tv', 'mp': '/tv', 'ro': '1'}
            }
        """
        if self.mock:
            logger.info(f"MOCK: Would get mounts for container {vmid}")
            return {}

        mounts = {}
        config = self.get_container_config(vmid)

        for key, value in config.items():
            if key.startswith('mp'):
                # Parse mount config: /tank/movies,mp=/movies,ro=1
                mount_info = self._parse_mount_config(value)
                if mount_info:
                    mounts[key] = mount_info

        return mounts

    def _parse_mount_config(self, config_str: str) -> Optional[Dict[str, str]]:
        """Parse a Proxmox mount configuration string.

        Args:
            config_str: Mount config like "/tank/movies,mp=/movies,ro=1"

        Returns:
            Dict with 'volume', 'mp', 'ro' keys, or None if parsing fails
        """
        try:
            parts = config_str.split(',')
            result = {'volume': parts[0].strip(), 'ro': '0'}

            for part in parts[1:]:
                if '=' in part:
                    key, val = part.split('=', 1)
                    result[key.strip()] = val.strip()

            return result
        except Exception as e:
            logger.warning(f"Failed to parse mount config '{config_str}': {e}")
            return None

    def add_container_mount(self, vmid: int, mount_point: int,
                           host_path: str, container_path: str,
                           readonly: bool = False) -> bool:
        """Add a mount point to a container.

        Checks for existing mounts at the same path and handles conflicts.
        Makes the operation idempotent.

        Args:
            vmid: Container ID
            mount_point: Mount point number (e.g., 0 for mp0)
            host_path: Path on the host (e.g., '/tank/movies')
            container_path: Path inside container (e.g., '/movies')
            readonly: Whether mount should be read-only

        Returns:
            True if mount added or already exists with same config
        """
        if self.mock:
            logger.info(f"MOCK: Would add mount to container {vmid}: {host_path} -> {container_path}")
            return True

        # Check if container exists
        if not self.container_exists(vmid):
            logger.error(f"Container {vmid} not found")
            return False

        # Check existing mounts
        existing_mounts = self.get_container_mounts(vmid)

        # Check if this specific mount point already exists
        mp_key = f"mp{mount_point}"
        if mp_key in existing_mounts:
            existing = existing_mounts[mp_key]
            ro_match = existing.get('ro', '0') == ('1' if readonly else '0')

            if existing['volume'] == host_path and existing['mp'] == container_path and ro_match:
                logger.info(f"Mount {mp_key} already configured correctly in container {vmid}")
                return True
            else:
                logger.warning(f"Mount {mp_key} exists with different config, updating...")
                # Fall through to update it

        # Check if container_path is already mounted elsewhere
        for mp_id, mount_info in existing_mounts.items():
            if mount_info['mp'] == container_path and mp_id != mp_key:
                logger.warning(f"Path {container_path} already mounted as {mp_id} in container {vmid}")
                logger.warning(f"  Existing: {mount_info['volume']} -> {container_path}")
                logger.warning(f"  Requested: {host_path} -> {container_path}")
                return False

        try:
            # Build mount options
            mount_spec = f"{host_path},mp={container_path}"
            if readonly:
                mount_spec += ",ro=1"

            # Add/update mount point using pct
            cmd = ["pct", "set", str(vmid), f"-mp{mount_point}", mount_spec]

            logger.info(f"Adding mount point to container {vmid}: mp{mount_point}={mount_spec}")
            subprocess.run(cmd, check=True)

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add container mount: {e}")
            return False

    def remove_container_mount(self, vmid: int, mount_point: int) -> bool:
        """Remove a mount point from a container."""
        if self.mock:
            logger.info(f"MOCK: Would remove mp{mount_point} from container {vmid}")
            return True

        try:
            # Use pct to remove the mount point
            cmd = ["pct", "set", str(vmid), f"-delete", f"mp{mount_point}"]

            logger.info(f"Removing mount point mp{mount_point} from container {vmid}")
            subprocess.run(cmd, check=True)

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to remove container mount: {e}")
            return False

    def find_container_by_name(self, name: str) -> Optional[int]:
        """Find container VMID by name."""
        containers = self.list_containers()
        for container in containers:
            if container.get('name') == name:
                return container['vmid']
        return None

    def get_container_info(self, vmid: int) -> Optional[Dict]:
        """Get detailed information about a container.
        
        Returns a dict with container details or None if not found:
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
            'mounts': self.get_container_mounts(vmid)
        }
        
        return info

    def get_container_by_name(self, name: str) -> Optional[Dict]:
        """Get detailed container info by name.
        
        Convenience method that combines find_container_by_name and get_container_info.
        """
        vmid = self.find_container_by_name(name)
        if vmid:
            return self.get_container_info(vmid)
        return None

    def get_all_containers_info(self) -> List[Dict]:
        """Get detailed info for all containers.
        
        Returns list of container info dicts.
        """
        containers = self.list_containers()
        result = []
        
        for container in containers:
            vmid = container['vmid']
            info = self.get_container_info(vmid)
            if info:
                result.append(info)
        
        return result

    def container_has_mount(self, vmid: int, host_path: str) -> bool:
        """Check if container already has a mount for the given host path.
        
        Args:
            vmid: Container ID
            host_path: Host path to check (e.g., '/tank/media')
            
        Returns:
            True if mount exists, False otherwise
        """
        if self.mock:
            return False
        
        mounts = self.get_container_mounts(vmid)
        for mount_config in mounts.values():
            if mount_config.get('volume') == host_path:
                return True
        return False

    def get_next_free_mountpoint(self, vmid: int) -> int:
        """Find the next available mount point number for a container."""
        if self.mock:
            return 0

        config = self.get_container_config(vmid)
        used_mps = []

        for key in config.keys():
            if key.startswith('mp'):
                try:
                    mp_num = int(key[2:])
                    used_mps.append(mp_num)
                except ValueError:
                    continue

        # Find first unused number starting from 0
        for i in range(256):  # Proxmox supports up to 256 mount points
            if i not in used_mps:
                return i

        raise ValueError(f"No free mount points available for container {vmid}")

    def setup_container_mounts(self, dataset_name: str, dataset_config: Dict,
                             pool: str = 'tank') -> List[Tuple[int, bool]]:
        """Set up all container mounts for a dataset.

        Returns list of (vmid, success) tuples.
        """
        results = []

        # Check if containers are configured
        containers = dataset_config.get('containers', [])
        if not containers:
            return results

        # Host path for the dataset
        host_path = f"/{pool}/{dataset_name}"

        for container_spec in containers:
            # Parse container specification
            if isinstance(container_spec, dict):
                container_name = container_spec.get('name')
                mount_path = container_spec.get('mount', f"/{dataset_name}")
                readonly = container_spec.get('readonly', False)
            elif isinstance(container_spec, str):
                # Simple format: "container_name:/mount/path"
                if ':' in container_spec:
                    container_name, mount_path = container_spec.split(':', 1)
                else:
                    container_name = container_spec
                    mount_path = f"/{dataset_name}"
                readonly = False
            else:
                logger.warning(f"Invalid container spec: {container_spec}")
                continue

            # Find container VMID
            vmid = self.find_container_by_name(container_name)
            if not vmid:
                logger.warning(f"Container '{container_name}' not found - skipping mount")
                logger.info(f"  Create the container first, then re-run 'tg apply'")
                results.append((0, False))
                continue

            # Find next available mount point
            mp_num = self.get_next_free_mountpoint(vmid)

            # Add the mount
            success = self.add_container_mount(
                vmid=vmid,
                mount_point=mp_num,
                host_path=host_path,
                container_path=mount_path,
                readonly=readonly
            )

            results.append((vmid, success))

            if success:
                logger.info(f"Successfully mounted {host_path} to {container_name}:{mount_path}")
            else:
                logger.error(f"Failed to mount {host_path} to {container_name}")

        return results
