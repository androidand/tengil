"""ZFS dataset management."""
import os
import subprocess
from typing import Dict, Optional

from tengil.core.logger import get_logger

logger = get_logger(__name__)

class ZFSManager:
    """Manages ZFS datasets and properties."""
    
    def __init__(self, mock: bool = False, state_store=None, permission_manager=None):
        self.mock = mock or os.environ.get('TG_MOCK', '').lower() in ('1', 'true')
        self._mock_datasets = set()  # Track datasets in mock mode
        self._state_store = state_store  # For checking persistent state
        self.permission_manager = permission_manager  # For managing ACLs and permissions
        
    def list_datasets(self, pool: str) -> Dict[str, Dict]:
        """List all datasets in a pool with their properties."""
        if self.mock:
            logger.info(f"MOCK: Would list datasets in {pool}")
            return {}

        try:
            datasets: Dict[str, Dict] = {}

            list_cmd = [
                "zfs",
                "list",
                "-H",
                "-p",
                "-r",
                "-o",
                "name,used,available,mountpoint",
                "-t",
                "filesystem",
                pool,
            ]
            list_result = subprocess.run(list_cmd, capture_output=True, text=True, check=True)

            for line in list_result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('\t')
                if len(parts) < 4:
                    continue
                name = parts[0]
                datasets[name] = {
                    'used': parts[1],
                    'available': parts[2],
                    'mountpoint': parts[3],
                }

            if not datasets:
                return {}

            props_cmd = [
                "zfs",
                "get",
                "-H",
                "-p",
                "-r",
                "-o",
                "name,property,value",
                "atime,compression,recordsize,sync",
                pool,
            ]
            props_result = subprocess.run(props_cmd, capture_output=True, text=True, check=True)

            for line in props_result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('\t')
                if len(parts) < 3:
                    continue
                name, prop, value = parts[0], parts[1], parts[2]
                dataset = datasets.get(name)
                if dataset is None:
                    # Dataset may exist but wasn't in list output (e.g., snapshot) - skip
                    continue
                if prop == 'recordsize':
                    value = self._format_recordsize(value)
                dataset[prop] = value

            # Ensure recordsize/compression keys exist even if zfs get skipped them
            for name, info in datasets.items():
                if 'recordsize' not in info:
                    info['recordsize'] = None
                if 'compression' not in info:
                    info['compression'] = None
                if 'atime' not in info:
                    info['atime'] = None
                if 'sync' not in info:
                    info['sync'] = None

            return datasets

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list datasets: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error while listing datasets: {e}")
            return {}

    @staticmethod
    def _format_recordsize(value: Optional[str]) -> Optional[str]:
        """Convert recordsize in bytes to human-readable unit (K/M/G)."""
        if value is None:
            return None

        try:
            size = int(value)
        except (TypeError, ValueError):
            return value

        units = ['', 'K', 'M', 'G', 'T', 'P']
        unit_index = 0
        while size % 1024 == 0 and unit_index < len(units) - 1:
            size //= 1024
            unit_index += 1

        if unit_index == 0:
            return str(size)
        return f"{size}{units[unit_index]}"
    
    def create_dataset(self, name: str, properties: Dict[str, str]) -> bool:
        """Create a ZFS dataset with specified properties.
        
        If the dataset already exists, syncs properties instead of failing.
        This makes the operation idempotent.
        
        Args:
            name: Full dataset name (e.g., 'tank/movies')
            properties: Dict of ZFS properties to set
            
        Returns:
            True if dataset created or properties synced successfully
        """
        # Check if dataset already exists
        if self.dataset_exists(name):
            logger.info(f"Dataset {name} already exists, syncing properties...")
            success = self.sync_properties(name, properties)
            # Apply permissions even if dataset already existed
            if success and self.permission_manager:
                self._apply_dataset_permissions(name)
            return success
        
        # Create new dataset
        if self.mock:
            logger.info(f"MOCK: Would create dataset {name} with properties {properties}")
            self._mock_datasets.add(name)
            # Apply permissions in mock mode too
            if self.permission_manager:
                self._apply_dataset_permissions(name)
            return True
            
        cmd = ["zfs", "create"]
        
        # Add properties as -o flags
        for key, value in properties.items():
            cmd.extend(["-o", f"{key}={value}"])
            
        cmd.append(name)
        
        try:
            logger.info(f"Creating dataset: {name}")
            subprocess.run(cmd, check=True)
            
            # Apply permissions after successful creation
            if self.permission_manager:
                self._apply_dataset_permissions(name)
            
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create dataset {name}: {e}")
            return False
    
    def set_property(self, dataset: str, key: str, value: str) -> bool:
        """Set a property on an existing dataset."""
        if self.mock:
            logger.info(f"MOCK: Would set {dataset} property {key}={value}")
            return True
            
        try:
            cmd = ["zfs", "set", f"{key}={value}", dataset]
            subprocess.run(cmd, check=True)
            logger.info(f"Set {dataset} property {key}={value}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set property: {e}")
            return False
    
    def get_properties(self, dataset: str) -> Dict[str, str]:
        """Get all properties for a dataset."""
        if self.mock:
            return {}
            
        try:
            cmd = ["zfs", "get", "-H", "-p", "all", dataset]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            properties = {}
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        properties[parts[1]] = parts[2]
                        
            return properties
        except subprocess.CalledProcessError:
            return {}
    
    def dataset_exists(self, dataset: str) -> bool:
        """Check if a dataset exists.
        
        Args:
            dataset: Full dataset name (e.g., 'tank/movies')
            
        Returns:
            True if dataset exists, False otherwise
        """
        if self.mock:
            # In mock mode, check both internal registry and state store
            if dataset in self._mock_datasets:
                return True
            # Check if dataset was created in previous runs
            if self._state_store and self._state_store.is_dataset_managed(dataset):
                self._mock_datasets.add(dataset)  # Add to registry for this session
                return True
            return False
        
        try:
            cmd = ["zfs", "list", "-H", "-o", "name", dataset]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def sync_properties(self, dataset: str, desired_properties: Dict[str, str]) -> bool:
        """Sync dataset properties to match desired state.
        
        Compares current properties with desired properties and updates
        only those that differ.
        
        Args:
            dataset: Full dataset name
            desired_properties: Dict of property key-value pairs to set
            
        Returns:
            True if all properties synced successfully
        """
        if self.mock:
            logger.info(f"MOCK: Would sync properties for {dataset}")
            for key, value in desired_properties.items():
                logger.info(f"MOCK:   {key}={value}")
            return True
        
        current_properties = self.get_properties(dataset)
        success = True
        changed = False
        
        for key, desired_value in desired_properties.items():
            current_value = current_properties.get(key)
            
            if current_value != desired_value:
                logger.info(f"Property mismatch for {dataset}: {key} is '{current_value}', want '{desired_value}'")
                if self.set_property(dataset, key, desired_value):
                    changed = True
                else:
                    logger.error(f"Failed to set {key}={desired_value} on {dataset}")
                    success = False
            else:
                logger.debug(f"Property {key} already set to {desired_value}")
        
        if not changed:
            logger.info(f"All properties for {dataset} already match desired state")
        
        return success

    def _apply_dataset_permissions(self, dataset: str) -> bool:
        """Apply permissions to a dataset using the PermissionManager.
        
        Retrieves ACL commands from the permission manager and executes them
        to set proper ownership and permissions on the dataset mountpoint.
        
        Args:
            dataset: Full dataset name (e.g., 'tank/movies')
            
        Returns:
            True if permissions applied successfully or no permissions configured
        """
        if not self.permission_manager:
            return True
        
        try:
            # Get ACL commands from permission manager
            acl_commands = self.permission_manager.get_zfs_acl_commands(dataset)
            
            if not acl_commands:
                logger.debug(f"No permissions configured for {dataset}")
                return True
            
            # Execute each ACL command
            for cmd_str in acl_commands:
                if self.mock:
                    logger.info(f"MOCK: Would execute ACL command: {cmd_str}")
                else:
                    logger.info(f"Applying permissions: {cmd_str}")
                    cmd = cmd_str.split()
                    subprocess.run(cmd, check=True)
            
            logger.info(f"Successfully applied permissions to {dataset}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply permissions to {dataset}: {e}")
            return False
