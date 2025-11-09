"""Diff engine for comparing desired vs actual state."""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from tengil.core.logger import get_logger

logger = get_logger(__name__)

class ChangeType(Enum):
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    UNCHANGED = "unchanged"

@dataclass
class Change:
    """Represents a single configuration change."""
    dataset: str
    change_type: ChangeType
    properties: Dict[str, Tuple[Optional[str], Optional[str]]]  # key -> (old, new)
    
class DiffEngine:
    """Calculate differences between desired and actual state.
    
    Works with full dataset paths (pool/dataset/child) - doesn't need to know
    about pool structure, just compares dataset names.
    """
    
    def __init__(self, desired_datasets: Dict[str, Dict], current_state: Dict):
        """
        Args:
            desired_datasets: Map of full dataset names to their configs
                             e.g. {"tank/media": {...}, "rpool/appdata": {...}}
            current_state: Current ZFS state from zfs.list_datasets()
        """
        self.desired_datasets = desired_datasets
        self.current = current_state
        self.changes = []
        
    def calculate_diff(self) -> List[Change]:
        """Calculate all required changes."""
        self.changes = []
        
        # Check each desired dataset (already has full path like tank/media)
        for full_name, config in self.desired_datasets.items():
            if full_name not in self.current:
                # Dataset needs to be created
                properties = {}
                if 'zfs' in config:
                    for key, value in config['zfs'].items():
                        properties[key] = (None, value)
                        
                self.changes.append(Change(
                    dataset=full_name,
                    change_type=ChangeType.CREATE,
                    properties=properties
                ))
            else:
                # Dataset exists, check for property changes
                current_props = self.current[full_name]
                desired_props = config.get('zfs', {})
                
                prop_changes = {}
                for key, desired_value in desired_props.items():
                    current_value = current_props.get(key)
                    if current_value != desired_value:
                        prop_changes[key] = (current_value, desired_value)
                
                if prop_changes:
                    self.changes.append(Change(
                        dataset=full_name,
                        change_type=ChangeType.MODIFY,
                        properties=prop_changes
                    ))
                    
        return self.changes
    
    def format_plan(self) -> str:
        """Format changes as human-readable plan."""
        if not self.changes:
            return "No changes required. Infrastructure is up to date."
        
        lines = ["Tengil will perform the following actions:\n"]
        
        for change in self.changes:
            if change.change_type == ChangeType.CREATE:
                lines.append(f"  + {change.dataset} (will be created)")
                for key, (_, new) in change.properties.items():
                    lines.append(f"      {key}: {new}")
                    
            elif change.change_type == ChangeType.MODIFY:
                lines.append(f"  ~ {change.dataset} (will be modified)")
                for key, (old, new) in change.properties.items():
                    lines.append(f"      {key}: {old} -> {new}")
                    
        lines.append(f"\nPlan: {len(self.changes)} change(s) to apply")
        return "\n".join(lines)
