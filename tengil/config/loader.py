"""YAML configuration loader with profile inheritance."""
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from tengil.config.container_parser import ContainerParser
from tengil.config.desired_state import build_desired_state
from tengil.config.format_migrator import FormatMigrator
from tengil.config.profile_applicator import ProfileApplicator
from tengil.config.profiles import PROFILES
from tengil.config.share_parser import ShareParser
from tengil.config.validator import MultiPoolValidator
from tengil.core.app_repo_spec import AppRepoSpec, AppRepoSpecError, iter_app_repo_specs
from tengil.core.smart_permissions import (
    SmartPermissionEvent,
    apply_smart_defaults,
    validate_permissions,
)
from tengil.models.config import ConfigValidationError


class ConfigLoader:
    """Loads and processes Tengil configuration files."""

    smart_permission_events: List[SmartPermissionEvent]

    def __init__(self, config_path: str = "tengil.yml"):
        self.config_path = Path(config_path)
        self.raw_config = None
        self.processed_config = None
        self.validator = MultiPoolValidator()
        self.app_repos: List[AppRepoSpec] = []
        self.smart_permission_events = []
        self._desired_state_cache: Optional[Dict[str, Any]] = None
        # Phase 2: Modular helpers
        self.format_migrator: Optional[FormatMigrator] = None
        self.profile_applicator: Optional[ProfileApplicator] = None
        self.container_parser: Optional[ContainerParser] = None
        self.share_parser = ShareParser()

    @property
    def PROFILES(self) -> Dict[str, Dict[str, str]]:
        """Return available profiles for backwards compatibility."""
        return PROFILES

    def load(self) -> Dict[str, Any]:
        """Load YAML configuration from file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path) as f:
            self.raw_config = yaml.safe_load(f)

        # Handle empty config file
        if not self.raw_config:
            raise ConfigValidationError("Config file is empty. Run 'tg init' to create a config.")

        # Validate and fix deprecated formats BEFORE validation
        self.format_migrator = FormatMigrator(self.raw_config, str(self.config_path.parent))
        self.raw_config = self.format_migrator.migrate()

        # Validate multi-pool configuration
        self.validator.validate(self.raw_config)

        self.processed_config = self._process_config(self.raw_config)
        self._desired_state_cache = None
        return self.processed_config

    def _process_config(self, config: Dict) -> Dict:
        """Apply profiles and inheritance to configuration."""
        processed = config.copy()

        # Initialize helpers with config
        self.profile_applicator = ProfileApplicator()
        self.container_parser = ContainerParser(processed)

        # Process pools (v2 format)
        if 'pools' in processed:
            for pool_name, pool_config in processed['pools'].items():
                if 'datasets' in pool_config:
                    # First pass: expand nested datasets
                    pool_config['datasets'] = self.profile_applicator.expand_nested_datasets(
                        pool_config['datasets']
                    )

                    for name, dataset in pool_config['datasets'].items():
                        # Apply profile if specified
                        if 'profile' in dataset:
                            self.profile_applicator.apply_profile(dataset)

                        dataset_path = f"{pool_name}/{name}"
                        if 'profile' not in dataset:
                            warnings.warn(
                                (
                                    f"Dataset '{dataset_path}' does not define a profile. "
                                    "Smart permission defaults will assume conservative readonly access."
                                ),
                                UserWarning,
                                stacklevel=2,
                            )

                        containers = dataset.get('containers', [])
                        explicit_readonly = self.container_parser.capture_explicit_readonly(containers)

                        events: List[SmartPermissionEvent] = []
                        apply_smart_defaults(dataset, dataset_path, events=events)

                        self.container_parser.strip_inferred_readonly(
                            containers, explicit_readonly, dataset.get('profile')
                        )

                        if events:
                            self.smart_permission_events.extend(events)

                        for warning_message in validate_permissions(dataset, dataset_path):
                            warnings.warn(warning_message, UserWarning, stacklevel=2)

        # Parse application repository specifications (Epic 1)
        self.app_repos = self._parse_app_repos(processed)

        return processed

    def get_pools(self) -> Dict[str, Any]:
        """Return all pools configuration."""
        return self.processed_config.get('pools', {})

    def get_app_repos(self) -> List[AppRepoSpec]:
        """Return configured app repository specifications."""
        return list(self.app_repos)

    def get_smart_permission_events(self) -> List[SmartPermissionEvent]:
        """Return telemetry emitted during smart permission inference."""
        return list(self.smart_permission_events)

    def build_desired_state(self) -> Dict[str, Any]:
        """Return the normalized desired-state representation of the config."""
        if self.processed_config is None:
            raise ConfigValidationError("Configuration not loaded; call load() before building desired state.")

        if self._desired_state_cache is None:
            self._desired_state_cache = build_desired_state(
                self.processed_config,
                str(self.config_path),
            )
        return self._desired_state_cache

    def _parse_app_repos(self, config: Dict[str, Any]) -> List[AppRepoSpec]:
        """Parse app repository specifications from config."""
        apps_section = config.get('apps')
        if not isinstance(apps_section, dict):
            return []

        repos_section = apps_section.get('repos')
        if repos_section is None:
            return []

        if not isinstance(repos_section, list):
            raise ConfigValidationError("'apps.repos' must be a list of repository definitions")

        base_path: Optional[Path] = self.config_path.parent if self.config_path else None
        try:
            return iter_app_repo_specs(repos_section, base_path=base_path)
        except AppRepoSpecError as exc:
            raise ConfigValidationError(f"Invalid app repo specification: {exc}") from exc

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
