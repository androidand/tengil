"""State persistence for tracking changes."""
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
from tengil.core.logger import get_logger

logger = get_logger(__name__)

class StateStore:
    """Track resources managed by Tengil.
    
    Maintains a state file to distinguish between resources created by Tengil
    and pre-existing resources. This enables:
    - Idempotent operations (safe to run multiple times)
    - Proper cleanup (don't delete pre-existing resources)
    - Change tracking and auditing
    """
    
    def __init__(self, state_file: Optional[Path] = None):
        """Initialize state store.
        
        Args:
            state_file: Path to state file. Defaults to .tengil/state.json
        """
        if state_file is None:
            state_file = Path.cwd() / ".tengil" / "state.json"
        
        self.state_file = Path(state_file)
        self.enabled = not os.environ.get('TG_STATELESS')
        self.state = self._load()
    
    def _load(self) -> dict:
        """Load state from file.
        
        Returns:
            State dict with datasets, mounts, shares, and external resources
        """
        if not self.state_file.exists():
            return self._empty_state()
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                logger.debug(f"Loaded state from {self.state_file}")
                return state
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load state file: {e}, using empty state")
            return self._empty_state()
    
    def _empty_state(self) -> dict:
        """Create empty state structure."""
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "datasets": {},
            "mounts": {},
            "shares": {
                "smb": {},
                "nfs": {}
            },
            "external": {
                "datasets": [],
                "mounts": {},
                "shares": {
                    "smb": [],
                    "nfs": []
                }
            }
        }
    
    def save(self) -> bool:
        """Save state to file.
        
        Returns:
            True if saved successfully
        """
        if not self.enabled:
            logger.debug("State tracking disabled (TG_STATELESS)")
            return False
        
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Update timestamp
            self.state["updated_at"] = datetime.now().isoformat()
            
            # Write atomically (write to temp, then rename)
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            
            temp_file.rename(self.state_file)
            logger.debug(f"Saved state to {self.state_file}")
            return True
            
        except (IOError, OSError) as e:
            logger.error(f"Failed to save state: {e}")
            return False
    
    # Dataset tracking
    
    def mark_dataset_managed(self, dataset_name: str, created: bool = True) -> None:
        """Mark dataset as managed by Tengil.
        
        Args:
            dataset_name: Full dataset name (e.g., 'tank/movies')
            created: True if created by Tengil, False if pre-existing
        """
        self.state['datasets'][dataset_name] = {
            'created_by_tengil': created,
            'timestamp': datetime.now().isoformat()
        }
        self.save()
    
    def is_managed_dataset(self, dataset_name: str) -> bool:
        """Check if dataset is managed by Tengil.
        
        Args:
            dataset_name: Full dataset name
            
        Returns:
            True if Tengil is managing this dataset
        """
        return dataset_name in self.state['datasets']
    
    # Alias for clarity
    def is_dataset_managed(self, dataset_name: str) -> bool:
        """Alias for is_managed_dataset."""
        return self.is_managed_dataset(dataset_name)
    
    def was_created_by_tengil(self, dataset_name: str) -> bool:
        """Check if dataset was originally created by Tengil.
        
        Args:
            dataset_name: Full dataset name
            
        Returns:
            True if Tengil created it, False if it was pre-existing
        """
        dataset_info = self.state['datasets'].get(dataset_name, {})
        return dataset_info.get('created_by_tengil', False)
    
    def mark_external_dataset(self, dataset_name: str) -> None:
        """Mark dataset as pre-existing (not created by Tengil).
        
        Args:
            dataset_name: Full dataset name
        """
        if dataset_name not in self.state['external']['datasets']:
            self.state['external']['datasets'].append(dataset_name)
            logger.info(f"Marked {dataset_name} as external (pre-existing)")
        self.save()
    
    def get_managed_datasets(self) -> List[str]:
        """Get list of all datasets managed by Tengil.
        
        Returns:
            List of dataset names
        """
        return list(self.state['datasets'].keys())
    
    def get_created_datasets(self) -> List[str]:
        """Get datasets that were created by Tengil (not pre-existing).
        
        Returns:
            List of dataset names created by Tengil
        """
        return [
            name for name, info in self.state['datasets'].items()
            if info.get('created_by_tengil', False)
        ]
    
    def get_external_datasets(self) -> List[str]:
        """Get list of external (pre-existing) datasets.
        
        Returns:
            List of external dataset names
        """
        return self.state['external']['datasets']
    
    # Mount tracking
    
    def mark_mount_managed(self, container_id: int, mount_point: str, 
                          dataset: str, created: bool = True) -> None:
        """Mark container mount as managed.
        
        Args:
            container_id: Container VMID
            mount_point: Mount path in container
            dataset: Dataset being mounted
            created: True if created by Tengil
        """
        container_key = str(container_id)
        if container_key not in self.state['mounts']:
            self.state['mounts'][container_key] = {}
        
        self.state['mounts'][container_key][mount_point] = {
            'dataset': dataset,
            'created_by_tengil': created,
            'timestamp': datetime.now().isoformat()
        }
        self.save()
    
    def is_managed_mount(self, container_id: int, mount_point: str) -> bool:
        """Check if mount is managed by Tengil.
        
        Args:
            container_id: Container VMID
            mount_point: Mount path
            
        Returns:
            True if managed by Tengil
        """
        container_key = str(container_id)
        return mount_point in self.state['mounts'].get(container_key, {})
    
    # Share tracking
    
    def mark_share_managed(self, share_type: str, share_name: str, 
                          dataset: str, created: bool = True) -> None:
        """Mark SMB/NFS share as managed.
        
        Args:
            share_type: 'smb' or 'nfs'
            share_name: Name of the share
            dataset: Dataset being shared
            created: True if created by Tengil
        """
        if share_type not in ['smb', 'nfs']:
            logger.warning(f"Invalid share type: {share_type}")
            return
        
        self.state['shares'][share_type][share_name] = {
            'dataset': dataset,
            'created_by_tengil': created,
            'timestamp': datetime.now().isoformat()
        }
        self.save()
    
    def is_managed_share(self, share_type: str, share_name: str) -> bool:
        """Check if share is managed by Tengil.
        
        Args:
            share_type: 'smb' or 'nfs'
            share_name: Share name
            
        Returns:
            True if managed by Tengil
        """
        if share_type not in ['smb', 'nfs']:
            return False
        return share_name in self.state['shares'][share_type]
    
    # Utility methods
    
    def should_track(self) -> bool:
        """Check if state tracking is enabled.
        
        Returns:
            True if should track state
        """
        return self.enabled and not self.is_ci_environment()
    
    def is_ci_environment(self) -> bool:
        """Check if running in CI environment.
        
        Returns:
            True if in CI
        """
        ci_vars = ['CI', 'CONTINUOUS_INTEGRATION', 'GITHUB_ACTIONS']
        return any(os.environ.get(var) for var in ci_vars)
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about managed resources.
        
        Returns:
            Dict with counts of managed resources
        """
        return {
            'datasets_managed': len(self.state['datasets']),
            'datasets_created': len(self.get_created_datasets()),
            'datasets_external': len(self.state['external']['datasets']),
            'mounts_managed': sum(len(mounts) for mounts in self.state['mounts'].values()),
            'smb_shares': len(self.state['shares']['smb']),
            'nfs_shares': len(self.state['shares']['nfs'])
        }
    
    def clear(self) -> None:
        """Clear all state (for testing/cleanup)."""
        self.state = self._empty_state()
        if self.state_file.exists():
            self.state_file.unlink()
        logger.info("Cleared state")
