"""Configuration validation logic."""
import re
from typing import Dict, List, Any

from tengil.models.config import ConfigValidationError


class MultiPoolValidator:
    """Validates multi-pool configuration."""

    def validate(self, config: Dict) -> None:
        """Validate multi-pool configuration.

        Raises:
            ConfigValidationError: If validation fails
        """
        errors = []
        warnings = []

        if 'pools' not in config:
            return

        all_dataset_names = []

        for pool_name, pool_config in config['pools'].items():
            # Validate pool name
            pool_errors = self._validate_pool_name(pool_name)
            errors.extend(pool_errors)

            # Check for Proxmox reserved paths on rpool
            if pool_name.lower() == 'rpool':
                rpool_warnings = self._check_rpool_safety(pool_config.get('datasets', {}))
                warnings.extend(rpool_warnings)

            # Validate datasets in this pool
            if 'datasets' in pool_config:
                dataset_errors = self._validate_dataset_names(pool_config['datasets'])
                errors.extend([f"Pool '{pool_name}': {err}" for err in dataset_errors])

                # Validate container specifications in each dataset
                for dataset_name, dataset_config in pool_config['datasets'].items():
                    if 'containers' in dataset_config and dataset_config['containers']:
                        dataset_path = f"{pool_name}/{dataset_name}"
                        container_errors = self._validate_container_specs(
                            dataset_config['containers'],
                            dataset_path
                        )
                        errors.extend(container_errors)

                # Collect all dataset names
                all_dataset_names.extend(
                    [(pool_name, name) for name in pool_config['datasets'].keys()]
                )

        # Check for cross-pool hardlink issues
        hardlink_warnings = self._check_hardlink_issues(config['pools'])
        warnings.extend(hardlink_warnings)

        if errors:
            error_msg = "Configuration validation failed:\n  " + "\n  ".join(errors)
            raise ConfigValidationError(error_msg)

        if warnings:
            import logging
            logger = logging.getLogger(__name__)
            for warning in warnings:
                logger.warning(warning)

    def _validate_pool_name(self, name: str) -> List[str]:
        """Validate ZFS pool name according to ZFS naming rules."""
        errors = []

        if not name:
            errors.append("Pool name cannot be empty")
            return errors

        # Check reserved words
        reserved = ['mirror', 'raidz', 'raidz1', 'raidz2', 'raidz3',
                   'spare', 'log', 'cache', 'special', 'dedup']
        if name.lower() in reserved:
            errors.append(f"Pool name '{name}' is a reserved ZFS keyword")

        # Check starts with hyphen or 'c' + number
        if name.startswith('-'):
            errors.append(f"Pool name '{name}' cannot start with hyphen")
        if len(name) >= 2 and name[0] == 'c' and name[1].isdigit():
            errors.append(f"Pool name '{name}' cannot start with 'c' followed by a number")

        # Check valid characters
        valid_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_:.')
        invalid_chars = set(name) - valid_chars
        if invalid_chars:
            errors.append(f"Pool name '{name}' contains invalid characters: {invalid_chars}")

        # Check length
        if len(name) > 256:
            errors.append(f"Pool name '{name}' exceeds maximum length of 256 characters")

        return errors

    def _validate_dataset_names(self, datasets: Dict[str, Any]) -> List[str]:
        """Validate dataset names against ZFS rules."""
        errors = []

        for name in datasets.keys():
            # Check for invalid characters
            if not re.match(r'^[a-zA-Z0-9/_.-]+$', name):
                errors.append(f"Dataset '{name}' contains invalid characters. "
                            f"Only alphanumeric, -, _, ., and / are allowed.")

            # Check length (ZFS max component length is 255 chars)
            parts = name.split('/')
            for part in parts:
                if len(part) > 255:
                    errors.append(f"Dataset component '{part}' exceeds 255 character limit")
                if len(part) == 0:
                    errors.append(f"Dataset '{name}' has empty component (double slash)")

            # Check for reserved names
            reserved = ['dump', 'swap']
            if name in reserved or any(part in reserved for part in parts):
                errors.append(f"Dataset '{name}' uses reserved name: {', '.join(reserved)}")

            # Check for leading/trailing slashes
            if name.startswith('/') or name.endswith('/'):
                errors.append(f"Dataset '{name}' must not start or end with '/'")

            # Check for special sequences that might cause issues
            if '..' in name:
                errors.append(f"Dataset '{name}' contains '..' which is not allowed")

        return errors

    def _check_rpool_safety(self, datasets: Dict[str, Any]) -> List[str]:
        """Check for Proxmox-reserved paths on rpool."""
        warnings = []
        reserved_prefixes = ['ROOT', 'data', 'var-lib-vz']

        for dataset_name in datasets.keys():
            # Check if dataset starts with reserved prefix
            first_component = dataset_name.split('/')[0]

            if first_component in reserved_prefixes:
                warnings.append(
                    f"🚨 Dataset 'rpool/{dataset_name}' uses Proxmox-reserved namespace!\n"
                    f"    '{first_component}' is managed by Proxmox and should not be modified.\n"
                    f"    This could break your Proxmox installation!\n"
                    f"    Recommendation: Use 'rpool/tengil/{dataset_name}' or another name."
                )

            # Suggest tengil namespace (but don't be annoying about it)
            elif first_component != 'tengil' and len(datasets) > 2:
                # Only show this once per config load, not per dataset
                if not any('💡 Consider' in w for w in warnings):
                    warnings.append(
                        f"💡 Consider using 'rpool/tengil/*' namespace for better organization.\n"
                        f"    Benefits: Easy backups, clear separation from Proxmox.\n"
                        f"    Your choice: This is optional - both approaches work!\n"
                        f"    See docs/USING_RPOOL.md for details."
                    )
                    break  # Only show once

        return warnings

    def _validate_container_specs(self, containers: List, dataset_path: str) -> List[str]:
        """Validate container specifications.
        
        Args:
            containers: List of container configurations
            dataset_path: Pool/dataset path for error messages
            
        Returns:
            List of validation errors
        """
        errors = []
        
        for idx, container in enumerate(containers):
            # String format: validate and continue
            if isinstance(container, str):
                parts = container.split(':')
                if len(parts) < 2:
                    errors.append(
                        f"Container {idx} in '{dataset_path}': invalid string format '{container}'\n"
                        f"    Expected: 'name:/mount' or 'name:/mount:ro'"
                    )
                continue
            
            # Should be dict format
            if not isinstance(container, dict):
                errors.append(
                    f"Container {idx} in '{dataset_path}' has invalid type: {type(container)}"
                )
                continue
            
            # Check identity (must have name or vmid)
            if not container.get('name') and not container.get('vmid'):
                errors.append(
                    f"Container {idx} in '{dataset_path}' must have 'name' or 'vmid'"
                )
            
            # Check mount point
            if not container.get('mount'):
                errors.append(
                    f"Container {idx} in '{dataset_path}' missing 'mount' field"
                )
            elif not container['mount'].startswith('/'):
                errors.append(
                    f"Container {idx} in '{dataset_path}': mount '{container['mount']}' "
                    f"must be absolute path (start with /)"
                )
            
            # Phase 2+ validation: auto_create requires template
            if container.get('auto_create'):
                if not container.get('template'):
                    errors.append(
                        f"Container {idx} in '{dataset_path}': auto_create=true requires 'template' field"
                    )
                
                # Validate resources if provided
                if 'resources' in container:
                    res = container['resources']
                    if not isinstance(res, dict):
                        errors.append(
                            f"Container {idx} in '{dataset_path}': resources must be a dict"
                        )
                    else:
                        # Check memory (MB)
                        if 'memory' in res and not isinstance(res['memory'], int):
                            errors.append(
                                f"Container {idx} in '{dataset_path}': resources.memory must be integer (MB)"
                            )
                        # Check cores
                        if 'cores' in res and not isinstance(res['cores'], int):
                            errors.append(
                                f"Container {idx} in '{dataset_path}': resources.cores must be integer"
                            )
                        # Check disk format
                        if 'disk' in res:
                            disk = str(res['disk'])
                            if not re.match(r'^\d+[GMgm]$', disk):
                                errors.append(
                                    f"Container {idx} in '{dataset_path}': resources.disk must be like '8G' or '512M'"
                                )
        
        return errors

    def _check_hardlink_issues(self, pools: Dict) -> List[str]:
        """Check for potential cross-pool hardlink issues."""
        warnings = []

        # Map containers to their mount points across all pools
        container_mounts = {}  # container_name -> [(pool, dataset, mount_path), ...]

        for pool_name, pool_config in pools.items():
            if 'datasets' not in pool_config:
                continue

            for dataset_name, dataset_config in pool_config['datasets'].items():
                if 'containers' not in dataset_config:
                    continue

                for container in dataset_config['containers']:
                    # Handle multiple container formats
                    if isinstance(container, str):
                        # String format: 'jellyfin:/media' or just 'jellyfin'
                        if ':' in container:
                            container_name, mount_path = container.split(':', 1)
                        else:
                            container_name = container
                            mount_path = ''
                    elif isinstance(container, dict):
                        # Dict format: prefer 'name', fall back to 'id' (deprecated)
                        container_name = container.get('name')
                        if not container_name:
                            # Skip containers with only 'id' - they'll get warning in loader.py
                            if 'id' in container:
                                continue
                            else:
                                # Invalid format - skip
                                continue
                        mount_path = container.get('mount', container.get('path', ''))
                    else:
                        # Invalid format - skip
                        continue

                    if container_name not in container_mounts:
                        container_mounts[container_name] = []

                    container_mounts[container_name].append(
                        (pool_name, dataset_name, mount_path)
                    )

        # Check *arr apps
        arr_apps = ['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr']

        for arr_app in arr_apps:
            if arr_app in container_mounts:
                mounts = container_mounts[arr_app]
                pools_used = set(pool for pool, _, _ in mounts)

                if len(pools_used) > 1:
                    pool_list = ', '.join(sorted(pools_used))
                    warnings.append(
                        f"⚠️  Container '{arr_app}' mounts from multiple pools: {pool_list}\n"
                        f"    This breaks hardlinks! *arr apps need downloads + media on the SAME pool.\n"
                        f"    Mounts: {', '.join(f'{pool}/{dataset}:{mount}' for pool, dataset, mount in mounts)}\n"
                        f"    Recommendation: Move all mounts to the same pool."
                    )

        return warnings
