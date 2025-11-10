"""Mount management for Proxmox LXC containers."""
import subprocess
from typing import Dict, Optional

from tengil.core.logger import get_logger
from .discovery import ContainerDiscovery

logger = get_logger(__name__)


class MountManager:
    """Manages mount points for LXC containers."""

    def __init__(self, mock: bool = False, permission_manager=None):
        self.mock = mock
        self.discovery = ContainerDiscovery(mock=mock)
        self.permission_manager = permission_manager  # For determining mount flags

    def get_container_mounts(self, vmid: int) -> Dict[str, Dict[str, str]]:
        """Get all mount points configured for a container.

        Args:
            vmid: Container ID

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
        config = self.discovery.get_container_config(vmid)

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
                           readonly: bool = False, container_name: str = None) -> bool:
        """Add a mount point to a container.

        Checks for existing mounts at the same path and handles conflicts.
        Makes the operation idempotent.

        Args:
            vmid: Container ID
            mount_point: Mount point number (e.g., 0 for mp0)
            host_path: Path on the host (e.g., '/tank/movies')
            container_path: Path inside container (e.g., '/movies')
            readonly: Whether mount should be read-only (can be overridden by permission_manager)
            container_name: Name of container (used for permission lookup)

        Returns:
            True if mount added or already exists with same config
        """
        # Check permission manager for readonly flag (overrides parameter)
        if self.permission_manager and container_name:
            try:
                flags = self.permission_manager.get_container_mount_flags(host_path, container_name)
                readonly = flags.get("readonly", readonly)
                logger.info(f"Permission manager determined readonly={readonly} for {container_name} -> {host_path}")
            except Exception as e:
                logger.warning(f"Could not get mount flags from permission manager: {e}, using readonly={readonly}")
        
        if self.mock:
            logger.info(f"MOCK: Would add mount to container {vmid}: {host_path} -> {container_path} (readonly={readonly})")
            return True

        # Check if container exists
        if not self.discovery.container_exists(vmid):
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
        """Remove a mount point from a container.

        Args:
            vmid: Container ID
            mount_point: Mount point number (e.g., 0 for mp0)

        Returns:
            True if successfully removed
        """
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
        """Find the next available mount point number for a container.

        Args:
            vmid: Container ID

        Returns:
            Next available mount point number

        Raises:
            ValueError: If no free mount points available
        """
        if self.mock:
            return 0

        config = self.discovery.get_container_config(vmid)
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
