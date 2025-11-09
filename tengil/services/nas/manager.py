"""Unified NAS management interface."""
import os
from pathlib import Path
from typing import Dict

from tengil.core.logger import get_logger
from tengil.services.nas.smb import SMBManager
from tengil.services.nas.nfs import NFSManager
from tengil.services.nas.acl import ACLManager

logger = get_logger(__name__)


class NASManager:
    """Manages SMB and NFS shares with proper permissions.

    This is a facade that delegates to specialized managers.
    """

    def __init__(self, mock: bool = False):
        self.mock = mock or os.environ.get('TG_MOCK', '').lower() in ('1', 'true')
        self.smb = SMBManager(mock=self.mock)
        self.nfs = NFSManager(mock=self.mock)
        self.acl = ACLManager(mock=self.mock)

    # ==================== SMB Management ====================

    def parse_smb_conf(self) -> Dict[str, Dict]:
        """Parse existing SMB configuration."""
        return self.smb.parse_smb_conf()

    def add_smb_share(self, name: str, path: str, config: Dict) -> bool:
        """Add or update an SMB share."""
        return self.smb.add_smb_share(name, path, config)

    def remove_smb_share(self, name: str) -> bool:
        """Remove an SMB share."""
        return self.smb.remove_smb_share(name)

    # ==================== NFS Management ====================

    def parse_nfs_exports(self) -> Dict[str, Dict]:
        """Parse existing NFS exports."""
        return self.nfs.parse_nfs_exports()

    def add_nfs_export(self, path: str, config: Dict) -> bool:
        """Add or update an NFS export."""
        return self.nfs.add_nfs_export(path, config)

    def remove_nfs_export(self, path: str) -> bool:
        """Remove an NFS export."""
        return self.nfs.remove_nfs_export(path)

    # ==================== ACL Management ====================

    def set_dataset_permissions(self, path: str, config: Dict) -> bool:
        """Set appropriate permissions and ACLs for a dataset."""
        return self.acl.set_dataset_permissions(path, config)

    # ==================== High-level Operations ====================

    def apply_dataset_nas_config(self, dataset_name: str, dataset_config: Dict,
                                pool: str = 'tank') -> bool:
        """Apply all NAS-related configuration for a dataset."""
        success = True
        dataset_path = f"/{pool}/{dataset_name}"

        # Ensure path exists
        if not Path(dataset_path).exists() and not self.mock:
            logger.warning(f"Dataset path does not exist: {dataset_path}")
            return False

        # Set permissions
        if 'permissions' in dataset_config:
            if not self.set_dataset_permissions(dataset_path, dataset_config['permissions']):
                success = False

        # Configure SMB share
        if 'shares' in dataset_config and 'smb' in dataset_config['shares']:
            smb_config = dataset_config['shares']['smb']

            # Handle both dict and string formats
            if isinstance(smb_config, str):
                smb_name = smb_config
                smb_options = {}
            else:
                smb_name = smb_config.get('name', dataset_name)
                smb_options = smb_config

            if not self.add_smb_share(smb_name, dataset_path, smb_options):
                success = False

        # Configure NFS export
        if 'shares' in dataset_config and 'nfs' in dataset_config['shares']:
            nfs_config = dataset_config['shares']['nfs']

            # Handle both dict and bool formats
            if isinstance(nfs_config, bool) and nfs_config:
                nfs_options = {}
            elif isinstance(nfs_config, dict):
                nfs_options = nfs_config
            else:
                nfs_options = None

            if nfs_options is not None:
                if not self.add_nfs_export(dataset_path, nfs_options):
                    success = False

        return success
