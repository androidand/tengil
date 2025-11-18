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

    def __init__(self, mock: bool = False, permission_manager=None):
        self.mock = mock or os.environ.get('TG_MOCK', '').lower() in ('1', 'true')
        self.permission_manager = permission_manager
        self.smb = SMBManager(mock=self.mock)
        self.nfs = NFSManager(mock=self.mock)
        self.acl = ACLManager(mock=self.mock)

    # ==================== SMB Management ====================

    def parse_smb_conf(self) -> Dict[str, Dict]:
        """Parse existing SMB configuration."""
        return self.smb.parse_smb_conf()

    def add_smb_share(self, name: str, path: str, config: Dict) -> bool:
        """Add or update an SMB share."""
        # Check permission manager for SMB share configuration
        if self.permission_manager:
            try:
                perm_config = self.permission_manager.get_smb_share_config(path, name)
                if perm_config:
                    # Merge permission manager config with provided config
                    config = {**perm_config, **config}
                    logger.info(f"Using permission manager config for SMB share {name}")
            except Exception as e:
                logger.warning(f"Could not get SMB config from permission manager: {e}")
        
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
            smb_entries = dataset_config['shares']['smb']

            # Allow single share or list of shares
            if isinstance(smb_entries, (list, tuple)):
                smb_iterable = smb_entries
            else:
                smb_iterable = [smb_entries]

            for entry in smb_iterable:
                if isinstance(entry, str):
                    smb_name = entry
                    smb_options = {}
                elif isinstance(entry, dict):
                    smb_name = entry.get('name', dataset_name)
                    smb_options = entry
                else:
                    logger.warning(
                        "Unsupported SMB share format for dataset %s: %s",
                        dataset_name,
                        entry,
                    )
                    success = False
                    continue

                if not self.add_smb_share(smb_name, dataset_path, smb_options):
                    success = False

        # Configure NFS export
        if 'shares' in dataset_config and 'nfs' in dataset_config['shares']:
            nfs_entries = dataset_config['shares']['nfs']

            if isinstance(nfs_entries, (list, tuple)):
                nfs_iterable = nfs_entries
            else:
                nfs_iterable = [nfs_entries]

            for entry in nfs_iterable:
                # Handle bool shorthand
                if isinstance(entry, bool):
                    if not entry:
                        continue
                    nfs_options = {}
                elif isinstance(entry, dict):
                    nfs_options = entry
                else:
                    logger.warning(
                        "Unsupported NFS export format for dataset %s: %s",
                        dataset_name,
                        entry,
                    )
                    success = False
                    continue

                if not self.add_nfs_export(dataset_path, nfs_options):
                    success = False

        return success
