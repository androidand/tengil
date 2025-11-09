"""Pool orchestration for multi-pool operations."""
from typing import Dict, Tuple

from tengil.config.loader import ConfigLoader
from tengil.core.zfs_manager import ZFSManager


class PoolOrchestrator:
    """Handles multi-pool operations and state flattening."""
    
    def __init__(self, loader: ConfigLoader, zfs: ZFSManager):
        """Initialize pool orchestrator.
        
        Args:
            loader: Configuration loader
            zfs: ZFS manager instance
        """
        self.loader = loader
        self.zfs = zfs
    
    def flatten_pools(self) -> Tuple[Dict[str, dict], Dict[str, dict]]:
        """Flatten all pools into desired and current state.
        
        Combines datasets from all pools into full-path dictionaries:
        - Desired: pool/dataset -> dataset_config
        - Current: pool/dataset -> current_properties
        
        Returns:
            Tuple of (all_desired, all_current) dictionaries
            
        Example:
            desired = {
                "tank/media": {"profile": "media", ...},
                "rpool/appdata": {"profile": "dev", ...}
            }
            current = {
                "tank/media": {"recordsize": "1M", ...}
            }
        """
        all_desired = {}
        all_current = {}
        
        pools = self.loader.get_pools()
        
        for pool_name, pool_config in pools.items():
            # Get current state for this pool
            current = self.zfs.list_datasets(pool_name)
            all_current.update(current)
            
            # Build full dataset paths (pool/dataset)
            for dataset_name, dataset_config in pool_config.get('datasets', {}).items():
                full_path = f"{pool_name}/{dataset_name}"
                all_desired[full_path] = dataset_config
        
        return all_desired, all_current
