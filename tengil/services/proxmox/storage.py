"""Proxmox storage configuration management."""
import subprocess
from pathlib import Path
from typing import Dict

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class StorageManager:
    """Manages Proxmox storage configuration."""

    def __init__(self, mock: bool = False):
        self.mock = mock
        self.storage_cfg_path = Path('/etc/pve/storage.cfg')

    def parse_storage_cfg(self) -> Dict[str, Dict]:
        """Parse /etc/pve/storage.cfg into a dictionary."""
        if self.mock:
            logger.info("MOCK: Would parse /etc/pve/storage.cfg")
            return {
                'local-zfs': {
                    'type': 'zfspool',
                    'pool': 'rpool/data',
                    'content': 'images,rootdir',
                    'sparse': '1'
                }
            }

        if not self.storage_cfg_path.exists():
            logger.warning(f"Storage config not found: {self.storage_cfg_path}")
            return {}

        storages = {}
        current_storage = None

        try:
            with open(self.storage_cfg_path) as f:
                for raw_line in f:
                    line = raw_line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue

                    # Storage definition starts (no indentation)
                    if ':' in line and not raw_line.startswith((' ', '\t')):
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            storage_type = parts[0].strip()
                            storage_name = parts[1].strip()
                            current_storage = storage_name
                            storages[storage_name] = {'type': storage_type}

                    # Storage properties (indented)
                    elif current_storage and raw_line.startswith((' ', '\t')):
                        # Handle both space and tab separated values
                        parts = line.split(None, 1)
                        if len(parts) == 2:
                            key, value = parts
                            storages[current_storage][key] = value
                        else:
                            # Handle properties without values or weird formatting
                            pass

        except Exception as e:
            logger.error(f"Failed to parse storage.cfg: {e}")

        return storages

    def add_storage_entry(self, name: str, config: Dict) -> bool:
        """Add a storage entry to /etc/pve/storage.cfg."""
        if self.mock:
            logger.info(f"MOCK: Would add storage '{name}' with config {config}")
            return True

        try:
            # Check if storage already exists
            existing = self.parse_storage_cfg()
            if name in existing:
                logger.info(f"Storage '{name}' already exists in storage.cfg")
                return True

            # Prepare storage entry
            lines = [f"\ndir: {name}\n"]

            # Default path based on dataset
            if 'path' not in config:
                pool = config.get('pool', 'tank')
                dataset = config.get('dataset', name)
                config['path'] = f"/{pool}/{dataset}"

            # Add configuration options
            for key, value in config.items():
                if key not in ['type', 'dataset', 'pool']:  # Skip meta keys
                    lines.append(f"\t{key} {value}\n")

            # Default content types if not specified
            if 'content' not in config:
                lines.append("\tcontent images,rootdir\n")

            # Write to storage.cfg
            with open(self.storage_cfg_path, 'a') as f:
                f.writelines(lines)

            logger.info(f"Added storage '{name}' to storage.cfg")

            # Reload Proxmox storage
            subprocess.run(["pvesm", "status"], capture_output=True)

            return True

        except Exception as e:
            logger.error(f"Failed to add storage entry: {e}")
            return False

    def validate_proxmox_environment(self) -> bool:
        """Check if we're running in a valid Proxmox environment."""
        if self.mock:
            return True

        # Check for Proxmox-specific paths and commands
        checks = [
            self.storage_cfg_path.exists(),
            Path('/usr/bin/pvesm').exists(),
            Path('/usr/sbin/pct').exists(),
            Path('/etc/pve').exists()
        ]

        if not all(checks):
            logger.warning("Not running in a Proxmox environment")
            return False

        return True
