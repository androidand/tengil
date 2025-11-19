"""Format migration and deprecation handling for configuration files.

Handles backward compatibility by detecting deprecated config formats and
auto-converting them to current standards while emitting helpful warnings.
"""
import warnings
from typing import Dict, Any

from tengil.models.config import ConfigValidationError
from tengil.config.container_parser import ContainerParser
from tengil.config.share_parser import ShareParser


class FormatMigrator:
    """Migrates deprecated config formats to current standards.
    
    This class handles all format validation, deprecation warnings, and
    automatic conversions to maintain backward compatibility while guiding
    users toward modern configuration patterns.
    """

    def __init__(self, config: Dict[str, Any], config_dir: str):
        """Initialize format migrator.
        
        Args:
            config: Raw configuration
            config_dir: Directory containing config file
        """
        self.config = config
        self.config_dir = config_dir
        self.container_parser = ContainerParser(config)
        self.share_parser = ShareParser()

    def migrate(self) -> Dict[str, Any]:
        """Migrate configuration from deprecated formats to current standard.

        Returns:
            Migrated configuration dictionary

        Raises:
            ConfigValidationError: For invalid formats that can't be auto-fixed
        """
        if 'pools' not in self.config:
            return self.config

        for pool_name, pool_config in self.config['pools'].items():
            if 'datasets' not in pool_config:
                continue

            for dataset_name, dataset_config in pool_config['datasets'].items():
                dataset_path = f"{pool_name}/{dataset_name}"

                # Migrate SMB/NFS from dataset level to shares section
                # Parse consumers section (Phase 3) - needed early for migration
                if 'consumers' in dataset_config:
                    # Import here to avoid circular dependency
                    from tengil.config.loader import ConfigLoader
                    loader = ConfigLoader()
                    dataset_config = loader._parse_consumers(dataset_config, dataset_path)

                dataset_config = self._migrate_shares_location(
                    dataset_config, dataset_name, dataset_path
                )

                # Fix container format (deprecated fields)
                if 'containers' in dataset_config:
                    dataset_config['containers'] = self.container_parser.fix_container_format(
                        dataset_config['containers'],
                        dataset_path
                    )
                    # Parse containers into structured format
                    dataset_config['containers'] = self.container_parser.parse_container_mounts(
                        dataset_config['containers'],
                        dataset_path
                    )
                    # Validate mount paths are absolute
                    self._validate_mount_paths(dataset_config['containers'], dataset_path)

                # Fix SMB configuration
                if 'shares' in dataset_config and 'smb' in dataset_config['shares']:
                    dataset_config['shares']['smb'] = self.share_parser.fix_smb_format(
                        dataset_config['shares']['smb'],
                        dataset_path
                    )

        return self.config

    def _migrate_shares_location(
        self, 
        dataset_config: Dict[str, Any],
        dataset_name: str,
        dataset_path: str
    ) -> Dict[str, Any]:
        """Migrate SMB/NFS from dataset root to shares section.

        Old format:
            dataset:
              smb: ShareName

        New format:
            dataset:
              shares:
                smb: ShareName
        """
        # Migrate SMB
        if 'smb' in dataset_config and 'shares' not in dataset_config:
            warnings.warn(
                f"Deprecated config format in '{dataset_path}':\n"
                f"  'smb:' should be under 'shares:'\n"
                f"  \n"
                f"  Current (deprecated):\n"
                f"    {dataset_name}:\n"
                f"      smb: ...\n"
                f"  \n"
                f"  Correct format:\n"
                f"    {dataset_name}:\n"
                f"      shares:\n"
                f"        smb: ...\n"
                f"  \n"
                f"  This format will be removed in v1.0",
                DeprecationWarning,
                stacklevel=4  # Adjust for call stack
            )
            # Auto-fix: move to 'shares'
            dataset_config['shares'] = {'smb': dataset_config.pop('smb')}

        # Migrate NFS
        if 'nfs' in dataset_config and 'shares' not in dataset_config:
            warnings.warn(
                f"Deprecated config format in '{dataset_path}':\n"
                f"  'nfs:' should be under 'shares:'\n"
                f"  This format will be removed in v1.0",
                DeprecationWarning,
                stacklevel=4  # Adjust for call stack
            )
            # Auto-fix: move to 'shares'
            if 'shares' not in dataset_config:
                dataset_config['shares'] = {}
            dataset_config['shares']['nfs'] = dataset_config.pop('nfs')

        return dataset_config

    def _validate_mount_paths(
        self,
        containers: list,
        dataset_path: str
    ) -> None:
        """Validate that all container mount paths are absolute.

        Args:
            containers: List of container configurations
            dataset_path: Dataset path for error messages

        Raises:
            ConfigValidationError: If any mount path is not absolute
        """
        for container in containers:
            if isinstance(container, dict) and 'mount' in container:
                mount = container['mount']
                if not mount.startswith('/'):
                    raise ConfigValidationError(
                        f"Invalid mount path in '{dataset_path}': '{mount}'\n"
                        f"  Mount paths must be absolute (start with '/').\n"
                        f"  Example: mount: /media"
                    )
