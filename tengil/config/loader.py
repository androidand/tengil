"""YAML configuration loader with profile inheritance."""
import yaml
import warnings
from pathlib import Path
from typing import Dict, Any, List

from tengil.models.config import ConfigValidationError
from tengil.config.profiles import PROFILES
from tengil.config.validator import MultiPoolValidator


class ConfigLoader:
    """Loads and processes Tengil configuration files."""

    def __init__(self, config_path: str = "tengil.yml"):
        self.config_path = Path(config_path)
        self.raw_config = None
        self.processed_config = None
        self.validator = MultiPoolValidator()

    @property
    def PROFILES(self) -> Dict[str, Dict[str, str]]:
        """Return available profiles for backwards compatibility."""
        return PROFILES

    def load(self) -> Dict[str, Any]:
        """Load YAML configuration from file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            self.raw_config = yaml.safe_load(f)

        # Handle empty config file
        if not self.raw_config:
            raise ConfigValidationError("Config file is empty. Run 'tg init' to create a config.")

        # Validate version
        if self.raw_config.get('version') != 2:
            raise ConfigValidationError("Only version 2 configs are supported. Please update your config.")

        # Validate and fix deprecated formats BEFORE validation
        self.raw_config = self._validate_and_fix_format(self.raw_config)

        # Validate multi-pool configuration
        self.validator.validate(self.raw_config)

        self.processed_config = self._process_config(self.raw_config)
        return self.processed_config

    def _process_config(self, config: Dict) -> Dict:
        """Apply profiles and inheritance to configuration."""
        processed = config.copy()

        # Process pools (v2 format)
        if 'pools' in processed:
            for pool_name, pool_config in processed['pools'].items():
                if 'datasets' in pool_config:
                    # First pass: expand nested datasets
                    pool_config['datasets'] = self._expand_nested_datasets(pool_config['datasets'])

                    for name, dataset in pool_config['datasets'].items():
                        # Apply profile if specified
                        if 'profile' in dataset:
                            self._apply_profile(dataset)

        return processed

    def _expand_nested_datasets(self, datasets: Dict[str, Any]) -> Dict[str, Any]:
        """Expand nested dataset notation (media/movies/4k) into explicit parent datasets."""
        expanded = {}

        # Collect all dataset paths
        all_paths = set(datasets.keys())

        # For each dataset with slashes, ensure parents exist
        for name in list(all_paths):
            parts = name.split('/')

            # Add all parent paths
            for i in range(1, len(parts)):
                parent_path = '/'.join(parts[:i])
                all_paths.add(parent_path)

        # Sort to ensure parents come before children
        sorted_paths = sorted(all_paths, key=lambda x: (x.count('/'), x))

        # Build expanded config
        for path in sorted_paths:
            if path in datasets:
                # User-defined dataset - use their config
                expanded[path] = datasets[path]
            else:
                # Auto-generated parent dataset - minimal config
                # Inherit profile from first child if possible
                child_profile = None
                for dataset_name, dataset_config in datasets.items():
                    if dataset_name.startswith(path + '/'):
                        child_profile = dataset_config.get('profile')
                        break

                expanded[path] = {
                    '_auto_parent': True,  # Mark as auto-generated
                    'profile': child_profile or 'media',  # Default to media profile
                    'zfs': {}
                }

        return expanded

    def _apply_profile(self, dataset: Dict):
        """Apply profile defaults to dataset configuration."""
        profile_name = dataset['profile']
        if profile_name in PROFILES:
            # Merge profile defaults with dataset config
            profile_defaults = PROFILES[profile_name].copy()

            # Dataset-specific ZFS settings override profile
            if 'zfs' not in dataset:
                dataset['zfs'] = {}

            for key, value in profile_defaults.items():
                if key not in dataset['zfs']:
                    dataset['zfs'][key] = value

    def get_pools(self) -> Dict[str, Any]:
        """Return all pools configuration."""
        return self.processed_config.get('pools', {})

    def _validate_and_fix_format(self, config: Dict) -> Dict:
        """Validate config format and auto-fix deprecated patterns.

        Emits deprecation warnings for old formats but auto-converts them to
        maintain backwards compatibility. Following Proxmox, ZFS, and Linux standards.

        Args:
            config: Raw configuration dict

        Returns:
            Fixed configuration dict

        Raises:
            ConfigValidationError: For invalid formats that can't be auto-fixed
        """
        if 'pools' not in config:
            return config

        for pool_name, pool_config in config['pools'].items():
            if 'datasets' not in pool_config:
                continue

            for dataset_name, dataset_config in pool_config['datasets'].items():
                dataset_path = f"{pool_name}/{dataset_name}"

                # NEW: Parse consumers section (Phase 3)
                if 'consumers' in dataset_config:
                    dataset_config = self._parse_consumers(
                        dataset_config,
                        dataset_path
                    )

                # Fix container mount configuration
                if 'containers' in dataset_config:
                    dataset_config['containers'] = self._fix_container_format(
                        dataset_config['containers'],
                        dataset_path
                    )
                    # Parse containers into structured format
                    dataset_config['containers'] = self._parse_container_mounts(
                        dataset_config['containers'],
                        dataset_path
                    )

                # Check for old 'smb'/'nfs' at dataset level (should be under 'shares')
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
                        stacklevel=2
                    )
                    # Auto-fix: move to 'shares'
                    dataset_config['shares'] = {'smb': dataset_config.pop('smb')}

                if 'nfs' in dataset_config and 'shares' not in dataset_config:
                    warnings.warn(
                        f"Deprecated config format in '{dataset_path}':\n"
                        f"  'nfs:' should be under 'shares:'\n"
                        f"  This format will be removed in v1.0",
                        DeprecationWarning,
                        stacklevel=2
                    )
                    # Auto-fix: move to 'shares'
                    if 'shares' not in dataset_config:
                        dataset_config['shares'] = {}
                    dataset_config['shares']['nfs'] = dataset_config.pop('nfs')

                # Fix SMB configuration
                if 'shares' in dataset_config and 'smb' in dataset_config['shares']:
                    dataset_config['shares']['smb'] = self._fix_smb_format(
                        dataset_config['shares']['smb'],
                        dataset_path
                    )

                # Validate mount paths are absolute
                if 'containers' in dataset_config:
                    for container in dataset_config['containers']:
                        if isinstance(container, dict) and 'mount' in container:
                            mount = container['mount']
                            if not mount.startswith('/'):
                                raise ConfigValidationError(
                                    f"Invalid mount path in '{dataset_path}': '{mount}'\n"
                                    f"  Mount paths must be absolute (start with '/').\n"
                                    f"  Example: mount: /media"
                                )

        return config

    def _parse_consumers(self, dataset_config: Dict, dataset_path: str) -> Dict:
        """Parse consumers section and convert to internal format.
        
        The consumers model (Phase 3) provides unified permission management.
        Consumers are converted to the existing internal format for backward compatibility,
        but stored separately for permission manager integration.
        
        Args:
            dataset_config: Dataset configuration dict
            dataset_path: Dataset path for error messages
        
        Returns:
            Modified dataset_config with consumers parsed and converted
        """
        consumers = dataset_config.get('consumers', [])
        if not consumers:
            return dataset_config
        
        # Keep raw consumers for permission manager
        dataset_config['_consumers'] = []
        
        # Convert consumers to existing internal structures
        if 'containers' not in dataset_config:
            dataset_config['containers'] = []
        if 'shares' not in dataset_config:
            dataset_config['shares'] = {}
        
        for idx, consumer in enumerate(consumers):
            if not isinstance(consumer, dict):
                raise ConfigValidationError(
                    f"Invalid consumer format in '{dataset_path}'[{idx}]: must be dict\n"
                    f"  Expected:\n"
                    f"    - type: container\n"
                    f"      name: jellyfin\n"
                    f"      access: read"
                )
            
            consumer_type = consumer.get('type')
            consumer_name = consumer.get('name')
            consumer_access = consumer.get('access')
            
            # Validate required fields
            if not consumer_type:
                raise ConfigValidationError(
                    f"Consumer in '{dataset_path}'[{idx}] missing 'type' field\n"
                    f"  Valid types: container, smb, nfs, user, group"
                )
            
            if not consumer_name:
                raise ConfigValidationError(
                    f"Consumer in '{dataset_path}'[{idx}] missing 'name' field"
                )
            
            if not consumer_access:
                raise ConfigValidationError(
                    f"Consumer in '{dataset_path}'[{idx}] missing 'access' field\n"
                    f"  Valid access levels: read, write"
                )
            
            # Validate access level
            if consumer_access not in ['read', 'write']:
                raise ConfigValidationError(
                    f"Invalid access level in '{dataset_path}'[{idx}]: '{consumer_access}'\n"
                    f"  Valid access levels: read, write"
                )
            
            # Store for permission manager
            dataset_config['_consumers'].append(consumer)
            
            # Convert to existing internal format for backward compatibility
            readonly = (consumer_access == 'read')
            
            if consumer_type == 'container':
                # Add to containers list
                container_spec = {
                    'name': consumer_name,
                    'mount': consumer.get('mount', f"/{dataset_path.split('/')[-1]}"),
                    'readonly': readonly,
                    '_from_consumer': True  # Mark as converted from consumer
                }
                dataset_config['containers'].append(container_spec)
            
            elif consumer_type == 'smb':
                # Add to shares.smb
                if 'smb' not in dataset_config['shares']:
                    dataset_config['shares']['smb'] = []
                
                # SMB can have multiple shares per dataset
                if not isinstance(dataset_config['shares']['smb'], list):
                    dataset_config['shares']['smb'] = [dataset_config['shares']['smb']]
                
                smb_config = {
                    'name': consumer_name,
                    'read only': 'yes' if readonly else 'no',
                    'writable': 'no' if readonly else 'yes',
                    '_from_consumer': True
                }
                dataset_config['shares']['smb'].append(smb_config)
            
            elif consumer_type == 'nfs':
                # Add to shares.nfs
                if 'nfs' not in dataset_config['shares']:
                    dataset_config['shares']['nfs'] = []
                
                if not isinstance(dataset_config['shares']['nfs'], list):
                    dataset_config['shares']['nfs'] = [dataset_config['shares']['nfs']]
                
                nfs_config = {
                    'name': consumer_name,
                    'readonly': readonly,
                    '_from_consumer': True
                }
                dataset_config['shares']['nfs'].append(nfs_config)
            
            elif consumer_type in ['user', 'group']:
                # User/group consumers are for ACLs only, don't convert to other structures
                pass
            
            else:
                raise ConfigValidationError(
                    f"Invalid consumer type in '{dataset_path}'[{idx}]: '{consumer_type}'\n"
                    f"  Valid types: container, smb, nfs, user, group"
                )
        
        return dataset_config

    def _fix_container_format(self, containers: List, dataset_path: str) -> List:
        """Fix deprecated container mount formats.

        Proxmox uses:
        - Container hostname ('name' field)
        - Mount points ('mp0', 'mp1', etc.)
        - Bind mounts from host to container

        Args:
            containers: List of container configurations
            dataset_path: Dataset path for error messages

        Returns:
            Fixed container list
        """
        if not containers:
            return containers

        fixed = []
        for idx, container in enumerate(containers):
            if isinstance(container, str):
                # String format is fine (e.g., 'jellyfin:/media')
                fixed.append(container)
                continue

            if not isinstance(container, dict):
                raise ConfigValidationError(
                    f"Invalid container format in '{dataset_path}': {container}\n"
                    f"  Must be either dict or string.\n"
                    f"  Examples:\n"
                    f"    - name: jellyfin\n"
                    f"      mount: /media\n"
                    f"    - 'jellyfin:/media'"
                )

            # Check for deprecated 'id' field (Proxmox VMID)
            if 'id' in container:
                warnings.warn(
                    f"Deprecated container format in '{dataset_path}':\n"
                    f"  Use 'name:' (container hostname) instead of 'id:' (VMID)\n"
                    f"  \n"
                    f"  Current (deprecated):\n"
                    f"    - id: {container['id']}\n"
                    f"      mount: {container.get('mount', '...')}\n"
                    f"  \n"
                    f"  Correct format:\n"
                    f"    - name: jellyfin  # Container hostname from Proxmox\n"
                    f"      mount: /media\n"
                    f"  \n"
                    f"  To find container name: pct config {container['id']} | grep hostname\n"
                    f"  This format will be removed in v1.0",
                    DeprecationWarning,
                    stacklevel=3
                )
                # Can't auto-fix - we don't know the container name from VMID

            # Check for deprecated 'path' field (should be 'mount')
            if 'path' in container:
                warnings.warn(
                    f"Deprecated container format in '{dataset_path}':\n"
                    f"  Use 'mount:' instead of 'path:'\n"
                    f"  \n"
                    f"  Current (deprecated):\n"
                    f"    - name: {container.get('name', '...')}\n"
                    f"      path: {container['path']}\n"
                    f"  \n"
                    f"  Correct format:\n"
                    f"    - name: {container.get('name', '...')}\n"
                    f"      mount: {container['path']}\n"
                    f"  \n"
                    f"  This format will be removed in v1.0",
                    DeprecationWarning,
                    stacklevel=3
                )
                # Auto-fix: rename 'path' to 'mount'
                container['mount'] = container.pop('path')

            fixed.append(container)

        return fixed

    def _parse_container_mounts(self, containers: List, dataset_path: str) -> List:
        """Parse and validate container configurations.
        
        Validates container specs but preserves original format for backward compatibility.
        
        Supports multiple formats:
        - Simple string: "jellyfin:/media" (kept as-is)
        - Dict with name: {name: jellyfin, mount: /media}
        - Dict with vmid: {vmid: 100, mount: /media}
        - Phase 2+: Full specs with auto_create, template, resources
        
        Args:
            containers: List of container configurations
            dataset_path: Dataset path for error messages
            
        Returns:
            List of validated containers (format preserved)
        """
        if not containers:
            return []
        
        parsed = []
        for container in containers:
            # String format: "name:/mount" or "name:/mount:ro"
            if isinstance(container, str):
                parts = container.split(':')
                if len(parts) < 2:
                    raise ConfigValidationError(
                        f"Invalid container string format in '{dataset_path}': {container}\n"
                        f"  Expected: 'name:/mount' or 'name:/mount:ro'"
                    )
                # Validate and keep string format
                parsed.append(container)
                continue
            
            # Dict format
            if not isinstance(container, dict):
                raise ConfigValidationError(
                    f"Invalid container type in '{dataset_path}': {type(container)}"
                )
            
            # Keep original dict mostly as-is, just validate
            container_data = container.copy()
            
            # Handle deprecated 'id' field (already warned in _fix_container_format)
            # Map 'id' to 'vmid' for internal consistency
            if 'id' in container_data and 'vmid' not in container_data:
                container_data['vmid'] = container_data['id']
            
            # Validate mount point
            if not container_data.get('mount'):
                raise ConfigValidationError(
                    f"Container in '{dataset_path}' missing required 'mount' field"
                )
            
            parsed.append(container_data)
        
        return parsed

    def _fix_smb_format(self, smb_config, dataset_path: str):
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
            if smb_config and all(isinstance(item, dict) and item.get('_from_consumer') for item in smb_config):
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
                    stacklevel=3
                )
                # Auto-fix: remove path
                smb_config.pop('path')

        return smb_config
