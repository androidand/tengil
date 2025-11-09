"""Unified Proxmox management interface."""
import os
from typing import Dict, List, Optional, Tuple

from tengil.core.logger import get_logger
from tengil.services.proxmox.storage import StorageManager
from tengil.services.proxmox.containers import ContainerManager

logger = get_logger(__name__)


class ProxmoxManager:
    """Manages Proxmox storage configuration and container mounts.

    This is a facade that delegates to specialized managers.
    """

    def __init__(self, mock: bool = False):
        self.mock = mock or os.environ.get('TG_MOCK', '').lower() in ('1', 'true')
        self.storage = StorageManager(mock=self.mock)
        self.containers = ContainerManager(mock=self.mock)

    # ==================== Storage Management ====================

    def parse_storage_cfg(self) -> Dict[str, Dict]:
        """Parse /etc/pve/storage.cfg into a dictionary."""
        return self.storage.parse_storage_cfg()

    def add_storage_entry(self, name: str, config: Dict) -> bool:
        """Add a storage entry to /etc/pve/storage.cfg."""
        return self.storage.add_storage_entry(name, config)

    def validate_proxmox_environment(self) -> bool:
        """Check if we're running in a valid Proxmox environment."""
        return self.storage.validate_proxmox_environment()

    # ==================== Container Management ====================

    def list_containers(self) -> List[Dict]:
        """List all LXC containers."""
        return self.containers.list_containers()

    def get_container_config(self, vmid: int) -> Dict:
        """Get configuration for a specific container."""
        return self.containers.get_container_config(vmid)

    def container_exists(self, vmid: int) -> bool:
        """Check if a container exists."""
        return self.containers.container_exists(vmid)

    def get_container_mounts(self, vmid: int) -> Dict[str, Dict[str, str]]:
        """Get all mount points configured for a container."""
        return self.containers.get_container_mounts(vmid)

    def add_container_mount(self, vmid: int, mount_point: int,
                           host_path: str, container_path: str,
                           readonly: bool = False) -> bool:
        """Add a mount point to a container."""
        return self.containers.add_container_mount(
            vmid, mount_point, host_path, container_path, readonly
        )

    def remove_container_mount(self, vmid: int, mount_point: int) -> bool:
        """Remove a mount point from a container."""
        return self.containers.remove_container_mount(vmid, mount_point)

    def find_container_by_name(self, name: str) -> Optional[int]:
        """Find container VMID by name."""
        return self.containers.find_container_by_name(name)

    def get_container_info(self, vmid: int) -> Optional[Dict]:
        """Get detailed information about a container."""
        return self.containers.get_container_info(vmid)

    def get_container_by_name(self, name: str) -> Optional[Dict]:
        """Get detailed container info by name."""
        return self.containers.get_container_by_name(name)

    def get_all_containers_info(self) -> List[Dict]:
        """Get detailed info for all containers."""
        return self.containers.get_all_containers_info()

    def container_has_mount(self, vmid: int, host_path: str) -> bool:
        """Check if container already has a mount for the given host path."""
        return self.containers.container_has_mount(vmid, host_path)

    def get_next_free_mountpoint(self, vmid: int) -> int:
        """Find the next available mount point number for a container."""
        return self.containers.get_next_free_mountpoint(vmid)

    def setup_container_mounts(self, dataset_name: str, dataset_config: Dict,
                             pool: str = 'tank') -> List[Tuple[int, bool]]:
        """Set up all container mounts for a dataset."""
        return self.containers.setup_container_mounts(dataset_name, dataset_config, pool)

    # ==================== High-level Operations ====================

    def apply_dataset_to_proxmox(self, dataset_name: str, dataset_config: Dict,
                                pool: str = 'tank') -> bool:
        """Apply all Proxmox-related configuration for a dataset."""
        if not self.validate_proxmox_environment() and not self.mock:
            logger.warning("Skipping Proxmox integration - not in Proxmox environment")
            return True

        success = True

        # Add to storage.cfg if needed
        if dataset_config.get('proxmox_storage', False):
            storage_config = {
                'path': f"/{pool}/{dataset_name}",
                'content': dataset_config.get('content', 'images,rootdir'),
                'shared': '1' if dataset_config.get('shared', False) else '0'
            }

            if not self.add_storage_entry(dataset_name, storage_config):
                success = False

        # Set up container mounts
        if 'containers' in dataset_config:
            mount_results = self.setup_container_mounts(dataset_name, dataset_config, pool)
            if mount_results and not all(r[1] for r in mount_results):
                success = False

        return success
