"""Diff engine for comparing desired vs actual state."""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

from tengil.core.logger import get_logger

logger = get_logger(__name__)

class ChangeType(Enum):
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    UNCHANGED = "unchanged"

class ContainerAction(Enum):
    """Container-specific actions."""
    CREATE = "create"  # Container will be created (auto_create=true)
    MOUNT_ONLY = "mount_only"  # Container exists, just mount
    EXISTS_OK = "exists_ok"  # Container exists with correct mounts

@dataclass
class Change:
    """Represents a single configuration change."""
    dataset: str
    change_type: ChangeType
    properties: Dict[str, Tuple[Optional[str], Optional[str]]]  # key -> (old, new)

@dataclass
class ContainerChange:
    """Represents a container-related change."""
    vmid: Optional[int]
    name: str
    action: ContainerAction
    template: Optional[str] = None
    mount_path: Optional[str] = None
    host_path: Optional[str] = None
    message: str = ""
    
class DiffEngine:
    """Calculate differences between desired and actual state.
    
    Works with full dataset paths (pool/dataset/child) - doesn't need to know
    about pool structure, just compares dataset names.
    """
    
    def __init__(self, desired_datasets: Dict[str, Dict], current_state: Dict, 
                 container_manager=None):
        """
        Args:
            desired_datasets: Map of full dataset names to their configs
                             e.g. {"tank/media": {...}, "rpool/appdata": {...}}
            current_state: Current ZFS state from zfs.list_datasets()
            container_manager: Optional ContainerOrchestrator for container diff detection
        """
        self.desired_datasets = desired_datasets
        self.current = current_state
        self.container_manager = container_manager
        self.changes = []
        self.container_changes = []
        
    def calculate_diff(self) -> List[Change]:
        """Calculate all required changes."""
        self.changes = []
        self.container_changes = []
        
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
        
        # Detect container changes if container manager is provided
        if self.container_manager:
            self._detect_container_changes()
                    
        return self.changes
    
    def _detect_container_changes(self):
        """Detect container changes across all datasets."""
        if not self.container_manager:
            return
        
        # Get list of existing containers
        try:
            existing_containers = self.container_manager.list_containers()
            existing_by_vmid = {c['vmid']: c for c in existing_containers}
            existing_by_name = {c['name']: c for c in existing_containers if c.get('name')}
        except Exception as e:
            logger.warning(f"Failed to list containers: {e}")
            return
        
        # Check each dataset for container configurations
        for full_name, config in self.desired_datasets.items():
            containers = config.get('containers', [])
            if not containers:
                continue
            
            # Extract pool name from full path (e.g., "tank/media" -> "tank")
            pool = full_name.split('/')[0]
            dataset_name = '/'.join(full_name.split('/')[1:]) if '/' in full_name else full_name
            host_path = f"/{full_name}"
            
            for container_spec in containers:
                if not isinstance(container_spec, dict):
                    continue
                
                vmid = container_spec.get('vmid')
                name = container_spec.get('name', '')
                auto_create = container_spec.get('auto_create', False)
                template = container_spec.get('template')
                mount_path = container_spec.get('mount', f"/{dataset_name}")
                
                # Determine if container exists
                existing = None
                if vmid and vmid in existing_by_vmid:
                    existing = existing_by_vmid[vmid]
                elif name and name in existing_by_name:
                    existing = existing_by_name[name]
                    vmid = existing['vmid']
                
                if not existing and auto_create:
                    # Container will be created
                    self.container_changes.append(ContainerChange(
                        vmid=vmid,
                        name=name,
                        action=ContainerAction.CREATE,
                        template=template,
                        mount_path=mount_path,
                        host_path=host_path,
                        message=f"will create from {template}"
                    ))
                elif existing:
                    # Container exists, check if mount needed
                    # For now, assume mount is needed (we'll check actual mounts in Phase 2.5)
                    self.container_changes.append(ContainerChange(
                        vmid=vmid or existing['vmid'],
                        name=name or existing['name'],
                        action=ContainerAction.MOUNT_ONLY,
                        mount_path=mount_path,
                        host_path=host_path,
                        message="exists, will mount"
                    ))
                elif not auto_create:
                    # Container specified but not found and auto_create=false
                    self.container_changes.append(ContainerChange(
                        vmid=vmid,
                        name=name,
                        action=ContainerAction.EXISTS_OK,
                        message="container not found (auto_create=false)"
                    ))
    
    def format_plan(self) -> str:
        """Format changes as human-readable plan."""
        if not self.changes and not self.container_changes:
            return "No changes required. Infrastructure is up to date."
        
        lines = ["Tengil will perform the following actions:\n"]
        
        # Dataset changes
        if self.changes:
            lines.append("Datasets:")
            for change in self.changes:
                if change.change_type == ChangeType.CREATE:
                    lines.append(f"  + {change.dataset} (will be created)")
                    for key, (_, new) in change.properties.items():
                        lines.append(f"      {key}: {new}")
                        
                elif change.change_type == ChangeType.MODIFY:
                    lines.append(f"  ~ {change.dataset} (will be modified)")
                    for key, (old, new) in change.properties.items():
                        lines.append(f"      {key}: {old} -> {new}")
            lines.append("")
        
        # Container changes
        if self.container_changes:
            lines.append("Containers:")
            for container in self.container_changes:
                vmid_str = f"{container.vmid}" if container.vmid else "auto"
                name_display = f"{container.name} ({vmid_str})"
                
                if container.action == ContainerAction.CREATE:
                    lines.append(f"  + {name_display} - {container.message}")
                    if container.mount_path:
                        lines.append(f"      mount: {container.host_path} → {container.mount_path}")
                elif container.action == ContainerAction.MOUNT_ONLY:
                    lines.append(f"  ✓ {name_display} - {container.message}")
                    if container.mount_path:
                        lines.append(f"      mount: {container.host_path} → {container.mount_path}")
            lines.append("")
                    
        total_changes = len(self.changes) + len(self.container_changes)
        lines.append(f"Plan: {total_changes} change(s) to apply")
        return "\n".join(lines)
