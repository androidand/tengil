"""Diff engine for comparing desired vs actual state."""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

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
    dataset: Optional[str] = None
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
        existing_by_vmid = {}
        existing_by_name = {}
        try:
            existing_containers = self.container_manager.list_containers()

            for container in existing_containers:
                vmid = container.get('vmid')
                name = container.get('name')

                if vmid is not None:
                    try:
                        existing_by_vmid[int(vmid)] = container
                    except (TypeError, ValueError):
                        logger.debug(f"Skipping container with non-numeric vmid: {vmid}")

                if name:
                    existing_by_name[name] = container
        except Exception as e:
            logger.warning(f"Failed to list containers: {e}. Assuming no containers exist.")
            existing_containers = []
        
        # Check each dataset for container configurations
        for full_name, config in self.desired_datasets.items():
            containers = config.get('containers', [])
            if not containers:
                continue

            dataset_name = '/'.join(full_name.split('/')[1:]) if '/' in full_name else full_name
            host_path = f"/{full_name}"

            for container_spec in containers:
                parsed = self._parse_container_spec(container_spec, dataset_name)
                if not parsed:
                    continue

                vmid_raw = parsed['vmid']
                name = parsed['name']
                auto_create = parsed['auto_create']
                template = parsed['template']
                mount_path = parsed['mount_path']
                readonly = parsed['readonly']

                vmid_int = None
                if vmid_raw is not None:
                    try:
                        vmid_int = int(vmid_raw)
                    except (TypeError, ValueError):
                        vmid_int = None

                existing = None
                resolved_vmid = None

                if vmid_int is not None and vmid_int in existing_by_vmid:
                    existing = existing_by_vmid[vmid_int]
                    resolved_vmid = vmid_int
                elif name and name in existing_by_name:
                    existing = existing_by_name[name]
                    resolved_vmid = existing.get('vmid')
                    if resolved_vmid is not None:
                        try:
                            resolved_vmid = int(resolved_vmid)
                        except (TypeError, ValueError):
                            resolved_vmid = None

                if not existing and auto_create:
                    self.container_changes.append(ContainerChange(
                        vmid=vmid_int,
                        name=name,
                        action=ContainerAction.CREATE,
                        template=template,
                        mount_path=mount_path,
                        host_path=host_path,
                        dataset=full_name,
                        message=f"will create from {template}" if template else "will create"
                    ))
                    continue

                if existing and resolved_vmid is not None:
                    if self._is_mount_configured(resolved_vmid, host_path, mount_path, readonly):
                        continue

                    self.container_changes.append(ContainerChange(
                        vmid=resolved_vmid,
                        name=name or existing.get('name', ''),
                        action=ContainerAction.MOUNT_ONLY,
                        mount_path=mount_path,
                        host_path=host_path,
                        dataset=full_name,
                        message="exists, will mount"
                    ))
                    continue

                if not existing and not auto_create:
                    self.container_changes.append(ContainerChange(
                        vmid=vmid_int,
                        name=name,
                        action=ContainerAction.EXISTS_OK,
                        host_path=host_path,
                        dataset=full_name,
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

    def _parse_container_spec(self, container_spec: Any, dataset_name: str) -> Optional[Dict[str, Any]]:
        """Normalize container specification into a standard dict."""
        default_mount = f"/{dataset_name}" if dataset_name else "/"

        if isinstance(container_spec, dict):
            return {
                'vmid': container_spec.get('vmid'),
                'name': container_spec.get('name', ''),
                'auto_create': bool(container_spec.get('auto_create', False)),
                'template': container_spec.get('template'),
                'mount_path': container_spec.get('mount', default_mount),
                'readonly': bool(container_spec.get('readonly', False))
            }

        if isinstance(container_spec, str):
            parts = container_spec.split(':')
            name = parts[0]
            mount_path = parts[1] if len(parts) > 1 and parts[1] else default_mount
            readonly_flag = parts[2] if len(parts) > 2 else ''
            readonly = readonly_flag.strip().lower() in {'ro', 'readonly', 'true', '1'}
            return {
                'vmid': None,
                'name': name,
                'auto_create': False,
                'template': None,
                'mount_path': mount_path,
                'readonly': readonly
            }

        logger.warning(f"Invalid container specification: {container_spec}")
        return None

    def _is_mount_configured(self, vmid: int, host_path: str, mount_path: str, readonly: bool) -> bool:
        """Return True if container already has matching mount configuration."""
        try:
            mounts = self.container_manager.get_container_mounts(vmid)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Failed to inspect mounts for container {vmid}: {exc}")
            return False

        desired_ro = '1' if readonly else '0'
        for mount_cfg in mounts.values():
            if mount_cfg.get('volume') != host_path:
                continue

            mp = mount_cfg.get('mp') or ''
            ro_flag = mount_cfg.get('ro', '0')

            if mp == mount_path and ro_flag == desired_ro:
                return True

        return False
