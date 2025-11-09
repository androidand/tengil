"""
Change application for Tengil infrastructure.

Handles applying calculated changes to the system by:
- Creating/modifying ZFS datasets
- Configuring container mounts
- Setting up NAS shares (SMB/NFS)
- Tracking state for created resources
"""

from typing import Dict, List
from rich.console import Console
from tengil.core.diff_engine import Change
from tengil.core.zfs_manager import ZFSManager
from tengil.services.proxmox import ProxmoxManager
from tengil.services.nas import NASManager
from tengil.core.state_store import StateStore


class ChangeApplicator:
    """Applies infrastructure changes to ZFS, Proxmox, and NAS systems."""
    
    def __init__(
        self,
        zfs: ZFSManager,
        proxmox: ProxmoxManager,
        nas: NASManager,
        state: StateStore,
        console: Console = None
    ):
        self.zfs = zfs
        self.proxmox = proxmox
        self.nas = nas
        self.state = state
        self.console = console or Console()
    
    def apply_changes(self, changes: List[Change], all_desired: Dict):
        """Apply all changes to the infrastructure.
        
        Args:
            changes: List of changes to apply
            all_desired: Full desired configuration for all datasets
        """
        self.console.print("\nApplying changes...")
        self.console.print("[dim]Note: Tengil never destroys datasets - only creates and configures[/dim]")
        
        for change in changes:
            if change.change_type.value == "create":
                self._apply_create(change, all_desired)
            elif change.change_type.value == "modify":
                self._apply_modify(change)
    
    def _apply_create(self, change: Change, all_desired: Dict):
        """Apply a CREATE change - create/sync dataset and configure integrations."""
        dataset_full_name = change.dataset  # e.g., tank/media or rpool/appdata
        
        # Extract pool and dataset name from full path
        parts = dataset_full_name.split('/')
        pool_name = parts[0]
        dataset_name = '/'.join(parts[1:])  # Handle nested like tank/media/4k
        
        # Get the config for this dataset
        dataset_config = all_desired.get(dataset_full_name, {})
        
        # Check current state of this dataset
        dataset_existed = self.zfs.dataset_exists(change.dataset)
        was_created_by_tengil = self.state.was_created_by_tengil(change.dataset)
        
        # Create ZFS dataset (or sync properties if exists)
        properties = {k: v[1] for k, v in change.properties.items()}
        if self.zfs.create_dataset(change.dataset, properties):
            # Report status based on whether dataset existed
            if dataset_existed:
                if was_created_by_tengil:
                    self.console.print(f"[green]✓[/green] Synced {change.dataset} (up to date)")
                    # Already tracked correctly, no state change needed
                else:
                    self.console.print(f"[green]✓[/green] Synced {change.dataset} (pre-existing)")
                    # Mark as external resource
                    self.state.mark_external_dataset(change.dataset)
                    self.state.mark_dataset_managed(change.dataset, created=False)
            else:
                self.console.print(f"[green]✓[/green] Created {change.dataset}")
                # Mark as created by Tengil
                self.state.mark_dataset_managed(change.dataset, created=True)
            
            # Apply Proxmox and NAS integrations if configured
            if dataset_config:
                self._setup_containers(change.dataset, dataset_name, dataset_config, pool_name)
                self._setup_nas_shares(change.dataset, dataset_name, dataset_config, pool_name)
        else:
            self.console.print(f"[red]✗[/red] Failed to create {change.dataset}")
    
    def _apply_modify(self, change: Change):
        """Apply a MODIFY change - update ZFS properties."""
        for key, (old, new) in change.properties.items():
            if self.zfs.set_property(change.dataset, key, new):
                self.console.print(f"[green]✓[/green] Set {change.dataset} {key}={new}")
            else:
                self.console.print(f"[red]✗[/red] Failed to set {change.dataset} {key}")
    
    def _setup_containers(self, dataset_full_name: str, dataset_name: str, 
                         dataset_config: Dict, pool_name: str):
        """Setup container mounts for a dataset."""
        if 'containers' not in dataset_config:
            return
        
        self.console.print(f"  [cyan]→[/cyan] Configuring container mounts...")
        results = self.proxmox.setup_container_mounts(dataset_name, dataset_config, pool_name)
        
        # Track successful mounts
        success_count = sum(1 for _, success in results if success)
        for vmid, success in results:
            if success and vmid > 0:
                # Find mount point from config
                for container in dataset_config['containers']:
                    if isinstance(container, dict):
                        mount_path = container.get('mount', f"/{dataset_name}")
                        self.state.mark_mount_managed(vmid, mount_path, dataset_full_name, created=True)
        
        if success_count > 0:
            self.console.print(f"  [green]✓[/green] Container mounts configured ({success_count} mounts)")
        else:
            self.console.print(f"  [yellow]⚠[/yellow] No container mounts configured")
    
    def _setup_nas_shares(self, dataset_full_name: str, dataset_name: str,
                         dataset_config: Dict, pool_name: str):
        """Setup NAS shares (SMB/NFS) for a dataset."""
        if 'shares' not in dataset_config:
            return
        
        self.console.print(f"  [cyan]→[/cyan] Configuring NAS shares...")
        if self.nas.apply_dataset_nas_config(dataset_name, dataset_config, pool_name):
            self.console.print(f"  [green]✓[/green] NAS shares configured")
            
            # Track shares in state
            if 'smb' in dataset_config['shares']:
                share_name = dataset_config['shares']['smb'].get('name', dataset_name)
                self.state.mark_share_managed('smb', share_name, dataset_full_name, created=True)
            if 'nfs' in dataset_config['shares']:
                self.state.mark_share_managed('nfs', dataset_name, dataset_full_name, created=True)
        else:
            self.console.print(f"  [yellow]⚠[/yellow] Some shares failed")
