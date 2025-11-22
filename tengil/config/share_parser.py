"""Share configuration parsing and validation.

Handles SMB (Samba) and NFS share configurations, including
format migrations and validation.
"""
import warnings
from typing import Any

from tengil.models.config import ConfigValidationError


class ShareParser:
    """Parses and validates SMB and NFS share configurations.
    
    Handles:
    - SMB (Samba) configuration validation
    - Deprecated format migrations (removing 'path' from SMB)
    - Consumer-based share configurations
    """

    @staticmethod
    def fix_smb_format(smb_config: Any, dataset_path: str) -> Any:
        """Fix deprecated SMB/Samba share formats.

        Samba configuration should NOT include 'path' - it's auto-calculated
        from the ZFS pool and dataset name.

        Args:
            smb_config: SMB configuration (dict, string, or list)
            dataset_path: Dataset path for error messages

        Returns:
            Fixed SMB configuration

        Raises:
            ConfigValidationError: For invalid formats
        """
        if isinstance(smb_config, list):
            # Lists are OK if they came from consumers (marked with _from_consumer)
            # But manual list format is deprecated
            if smb_config and all(
                isinstance(item, dict) and item.get('_from_consumer')
                for item in smb_config
            ):
                # This list came from consumers parsing, it's fine
                return smb_config

            # Manual list format is not allowed
            raise ConfigValidationError(
                f"Invalid SMB configuration in '{dataset_path}':\n"
                f"  SMB config must be a dict, not a list.\n"
                f"  \n"
                f"  Wrong format:\n"
                f"    shares:\n"
                f"      smb:\n"
                f"        - name: Media\n"
                f"  \n"
                f"  Correct format:\n"
                f"    shares:\n"
                f"      smb:\n"
                f"        name: Media\n"
                f"        browseable: yes\n"
                f"        guest_ok: false"
            )

        if isinstance(smb_config, dict):
            # Check for deprecated 'path' parameter
            if 'path' in smb_config:
                warnings.warn(
                    f"Deprecated SMB config in '{dataset_path}':\n"
                    f"  Remove 'path:' parameter - it's auto-calculated from dataset.\n"
                    f"  \n"
                    f"  The share path is always: /<pool>/<dataset>\n"
                    f"  For '{dataset_path}': path is auto-set to /{dataset_path}\n"
                    f"  \n"
                    f"  Current (deprecated):\n"
                    f"    smb:\n"
                    f"      name: {smb_config.get('name', 'ShareName')}\n"
                    f"      path: {smb_config['path']}  # REMOVE THIS\n"
                    f"  \n"
                    f"  Correct format:\n"
                    f"    smb:\n"
                    f"      name: {smb_config.get('name', 'ShareName')}\n"
                    f"      browseable: yes\n"
                    f"  \n"
                    f"  This will be an error in v1.0",
                    DeprecationWarning,
                    stacklevel=3,
                )
                # Auto-fix: remove path
                smb_config.pop('path')

        return smb_config
