"""
Change application for Tengil infrastructure.

Handles applying calculated changes to the system by:
- Creating/modifying ZFS datasets
- Configuring container mounts
- Setting up NAS shares (SMB/NFS)
- Tracking state for created resources
"""

from typing import Dict, List, Optional, Set, Tuple

from rich.console import Console

from tengil.core.diff_engine import Change, ContainerChange
from tengil.core.state_store import StateStore
from tengil.core.zfs_manager import ZFSManager
from tengil.services.nas import NASManager
from tengil.services.proxmox import ProxmoxManager


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
    
    def apply_changes(
        self,
        changes: List[Change],
        all_desired: Dict,
        container_changes: Optional[List[ContainerChange]] = None,
    ) -> None:
        """Apply all changes to the infrastructure.
        
        Args:
            changes: List of changes to apply
            all_desired: Full desired configuration for all datasets
            container_changes: Planned container actions detected by diff engine
        """
        container_changes = container_changes or []

        if not changes and not container_changes:
            self.console.print("\nApplying changes...")
            self.console.print("[dim]Nothing to do - infrastructure already aligned[/dim]")
            return

        self.console.print("\nApplying changes...")
        self.console.print("[dim]Note: Tengil never destroys datasets - only creates and configures[/dim]")

        handled_container_datasets: Set[str] = set()
        
        for change in changes:
            if change.change_type.value == "create":
                containers_handled = self._apply_create(change, all_desired)
                if containers_handled:
                    handled_container_datasets.add(change.dataset)
            elif change.change_type.value == "modify":
                self._apply_modify(change)

        if not container_changes:
            return

        for container_change in container_changes:
            dataset_full_name = container_change.dataset
            if not dataset_full_name and container_change.host_path:
                dataset_full_name = container_change.host_path.lstrip('/')

            if not dataset_full_name:
                continue

            if dataset_full_name in handled_container_datasets:
                continue

            dataset_config = all_desired.get(dataset_full_name)
            if not dataset_config:
                continue

            pool_name, dataset_name = self._split_dataset(dataset_full_name)

            if self._setup_containers(dataset_full_name, dataset_name, dataset_config, pool_name):
                handled_container_datasets.add(dataset_full_name)
    
    def _apply_create(self, change: Change, all_desired: Dict) -> bool:
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
        containers_handled = False

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
                if self._setup_containers(change.dataset, dataset_name, dataset_config, pool_name):
                    containers_handled = True
                self._setup_nas_shares(change.dataset, dataset_name, dataset_config, pool_name)
        else:
            self.console.print(f"[red]✗[/red] Failed to create {change.dataset}")

        return containers_handled
    
    def _apply_modify(self, change: Change):
        """Apply a MODIFY change - update ZFS properties."""
        for key, (old, new) in change.properties.items():
            if self.zfs.set_property(change.dataset, key, new):
                self.console.print(f"[green]✓[/green] Set {change.dataset} {key}={new}")
            else:
                self.console.print(f"[red]✗[/red] Failed to set {change.dataset} {key}")
    
    def _setup_containers(self, dataset_full_name: str, dataset_name: str, 
                         dataset_config: Dict, pool_name: str) -> bool:
        """Setup container mounts for a dataset (includes Phase 2 auto-creation)."""
        if 'containers' not in dataset_config:
            return False
        
        self.console.print("  [cyan]→[/cyan] Configuring containers...")
        results = self.proxmox.setup_container_mounts(dataset_name, dataset_config, pool_name)
        
        # Process results (vmid, success, message)
        success_count = 0
        created_count = 0
        
        for vmid, success, message in results:
            if success and vmid > 0:
                # Check if this was a creation or just a mount
                is_creation = "created" in message.lower()
                
                if is_creation:
                    created_count += 1
                    self.console.print(f"    [green]✓[/green] Container {vmid}: {message}")
                else:
                    self.console.print(f"    [green]✓[/green] Container {vmid}: {message}")
                
                # Find container spec from config for state tracking
                for container in dataset_config['containers']:
                    if isinstance(container, dict):
                        container_vmid = container.get('vmid')
                        container_name = container.get('name', '')
                        
                        # Match by vmid or name
                        if container_vmid == vmid or (container_name and vmid):
                            mount_path = container.get('mount', f"/{dataset_name}")
                            template = container.get('template', '')
                            
                            # Track mount
                            self.state.mark_mount_managed(vmid, mount_path, dataset_full_name, created=True)
                            
                            # Track container if it was created
                            if is_creation:
                                self.state.mark_container_managed(
                                    vmid=vmid,
                                    name=container_name,
                                    template=template,
                                    created=True,
                                    mounts=[mount_path]
                                )
                            elif not self.state.is_managed_container(vmid):
                                # Mark as managed but not created by us
                                self.state.mark_container_managed(
                                    vmid=vmid,
                                    name=container_name,
                                    template=template or "unknown",
                                    created=False,
                                    mounts=[mount_path]
                                )
                            break
                
                success_count += 1
            else:
                self.console.print(f"    [yellow]⚠[/yellow] Container {vmid if vmid else '?'}: {message}")
        
        if success_count > 0:
            summary = f"{success_count} container(s) configured"
            if created_count > 0:
                summary += f" ({created_count} created)"
            self.console.print(f"  [green]✓[/green] {summary}")
            return True

        self.console.print("  [yellow]⚠[/yellow] No containers configured successfully")
        return False
    
    def _setup_nas_shares(self, dataset_full_name: str, dataset_name: str,
                         dataset_config: Dict, pool_name: str):
        """Setup NAS shares (SMB/NFS) for a dataset."""
        if 'shares' not in dataset_config:
            return
        
        self.console.print("  [cyan]→[/cyan] Configuring NAS shares...")
        if self.nas.apply_dataset_nas_config(dataset_name, dataset_config, pool_name):
            self.console.print("  [green]✓[/green] NAS shares configured")
            
            # Track shares in state
            if 'smb' in dataset_config['shares']:
                smb_entries = dataset_config['shares']['smb']
                if isinstance(smb_entries, list):
                    for share in smb_entries:
                        name = share if isinstance(share, str) else share.get('name', dataset_name)
                        self.state.mark_share_managed('smb', name, dataset_full_name, created=True)
                else:
                    share = smb_entries
                    name = share if isinstance(share, str) else share.get('name', dataset_name)
                    self.state.mark_share_managed('smb', name, dataset_full_name, created=True)
            if 'nfs' in dataset_config['shares']:
                nfs_entries = dataset_config['shares']['nfs']
                if isinstance(nfs_entries, list):
                    for _ in nfs_entries:
                        self.state.mark_share_managed('nfs', dataset_name, dataset_full_name, created=True)
                else:
                    self.state.mark_share_managed('nfs', dataset_name, dataset_full_name, created=True)
        else:
            self.console.print("  [yellow]⚠[/yellow] Some shares failed")

    @staticmethod
    def _split_dataset(dataset_full_name: str) -> Tuple[str, Optional[str]]:
        """Split full dataset path into pool and dataset name."""
        if '/' not in dataset_full_name:
            return dataset_full_name, dataset_full_name
        pool, remainder = dataset_full_name.split('/', 1)
        return pool, remainder
