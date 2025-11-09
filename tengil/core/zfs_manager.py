"""ZFS dataset management."""
import subprocess
import json
from typing import Dict, List, Optional
from pathlib import Path
import os

from tengil.core.logger import get_logger

logger = get_logger(__name__)

class ZFSManager:
    """Manages ZFS datasets and properties."""
    
    def __init__(self, mock: bool = False, state_store=None):
        self.mock = mock or os.environ.get('TG_MOCK', '').lower() in ('1', 'true')
        self._mock_datasets = set()  # Track datasets in mock mode
        self._state_store = state_store  # For checking persistent state
        
    def list_datasets(self, pool: str) -> Dict[str, Dict]:
        """List all datasets in a pool with their properties."""
        if self.mock:
            logger.info(f"MOCK: Would list datasets in {pool}")
            return {}
            
        try:
            # Get all datasets with properties in JSON format
            cmd = ["zfs", "list", "-H", "-p", "-o", 
                   "name,used,available,mountpoint,compression,recordsize",
                   "-t", "filesystem", pool]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            datasets = {}
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    name = parts[0]
                    datasets[name] = {
                        'used': parts[1],
                        'available': parts[2],
                        'mountpoint': parts[3],
                        'compression': parts[4],
                        'recordsize': parts[5]
                    }
                    
            return datasets
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list datasets: {e}")
            return {}
    
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
            return self.sync_properties(name, properties)
        
        # Create new dataset
        if self.mock:
            logger.info(f"MOCK: Would create dataset {name} with properties {properties}")
            self._mock_datasets.add(name)
            return True
            
        cmd = ["zfs", "create"]
        
        # Add properties as -o flags
        for key, value in properties.items():
            cmd.extend(["-o", f"{key}={value}"])
            
        cmd.append(name)
        
        try:
            logger.info(f"Creating dataset: {name}")
            subprocess.run(cmd, check=True)
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
