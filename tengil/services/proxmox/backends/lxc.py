"""LXC container backend (traditional templates)."""
import subprocess
from typing import Dict, Optional
from rich.console import Console
from rich.status import Status
from .base import ContainerBackend

console = Console()


class LXCBackend(ContainerBackend):
    """LXC backend using traditional Proxmox templates."""

    def __init__(self, node: str = 'localhost', mock: bool = False):
        """Initialize LXC backend.
        
        Args:
            node: Proxmox node name
            mock: If True, simulate operations
        """
        super().__init__(mock)
        self.node = node

    def create_container(
        self,
        spec: Dict,
        storage: str = 'local-lvm',
        pool: Optional[str] = None,
        **kwargs
    ) -> Optional[int]:
        """Create LXC container from traditional template.
        
        Args:
            spec: Container specification
            storage: Storage backend for rootfs
            pool: Resource pool (optional)
            **kwargs: Additional options
            
        Returns:
            Container VMID or None if failed
        """
        # Get template
        template = spec.get('template')
        if not template:
            console.print("[red]✗[/red] No template specified")
            return None
        
        # Get or allocate VMID
        vmid = spec.get('vmid') or self._get_next_vmid()
        
        # Build pct create command
        cmd = ['pct', 'create', str(vmid), template]
        
        # Add basic options
        hostname = spec.get('hostname') or spec.get('name')
        if hostname:
            cmd.extend(['--hostname', hostname])
        
        # Resources
        cores = spec.get('cores') or spec.get('resources', {}).get('cores', 2)
        memory = spec.get('memory') or spec.get('resources', {}).get('memory', 2048)
        disk = spec.get('disk') or spec.get('resources', {}).get('disk', 8)
        
        cmd.extend([
            '--cores', str(cores),
            '--memory', str(memory),
            '--rootfs', f'{storage}:{disk}'
        ])
        
        # Network
        network = spec.get('network', {})
        bridge = network.get('bridge', 'vmbr0')
        ip = network.get('ip', 'dhcp')
        cmd.extend(['--net0', f'name=eth0,bridge={bridge},ip={ip}'])
        
        # Unprivileged
        if spec.get('unprivileged', True):
            cmd.append('--unprivileged')
            cmd.append('1')
        
        # Features
        features = spec.get('features', {})
        feature_str = ','.join(f'{k}={int(v)}' for k, v in features.items())
        if feature_str:
            cmd.extend(['--features', feature_str])
        
        # Pool
        if pool:
            cmd.extend(['--pool', pool])
        
        # Execute
        if self.mock:
            console.print(f"[dim][MOCK] Would run: {' '.join(cmd)}[/dim]")
            return vmid
        
        try:
            with console.status(f"[cyan]Creating container {vmid}...[/cyan]", spinner="dots"):
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )
            
            # Configure GPU if specified
            if spec.get('gpu', {}).get('passthrough') or features.get('gpu'):
                with console.status(f"[cyan]Configuring GPU for {vmid}...[/cyan]", spinner="dots"):
                    self.configure_gpu(vmid)
            
            # Add mounts
            mounts = spec.get('mounts', [])
            for mount in mounts:
                self._add_mount(vmid, mount)
            
            console.print(f"[green]✓[/green] Created container {vmid}")
            return vmid
            
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗[/red] Error creating container: {e.stderr}")
            return None

    def start_container(self, vmid: int) -> bool:
        """Start LXC container."""
        cmd = ['pct', 'start', str(vmid)]
        
        if self.mock:
            console.print(f"[dim][MOCK] Would run: {' '.join(cmd)}[/dim]")
            return True
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗[/red] Error starting container {vmid}: {e.stderr}")
            return False

    def stop_container(self, vmid: int, timeout: int = 30) -> bool:
        """Stop LXC container."""
        cmd = ['pct', 'stop', str(vmid), '--timeout', str(timeout)]
        
        if self.mock:
            console.print(f"[dim][MOCK] Would run: {' '.join(cmd)}[/dim]")
            return True
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗[/red] Error stopping container {vmid}: {e.stderr}")
            return False

    def destroy_container(self, vmid: int, purge: bool = False) -> bool:
        """Destroy LXC container."""
        cmd = ['pct', 'destroy', str(vmid)]
        if purge:
            cmd.append('--purge')
        
        if self.mock:
            console.print(f"[dim][MOCK] Would run: {' '.join(cmd)}[/dim]")
            return True
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗[/red] Error destroying container {vmid}: {e.stderr}")
            return False

    def container_exists(self, vmid: int) -> bool:
        """Check if container exists."""
        cmd = ['pct', 'status', str(vmid)]
        
        if self.mock:
            return False
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def configure_gpu(self, vmid: int, gpu_type: Optional[str] = None) -> bool:
        """Configure GPU passthrough."""
        devices = [
            ('--dev0', '/dev/dri/card0,mode=0666'),
            ('--dev1', '/dev/dri/renderD128,mode=0666')
        ]
        
        cmd = ['pct', 'set', str(vmid)]
        for flag, device in devices:
            cmd.extend([flag, device])
        
        if self.mock:
            console.print(f"[dim][MOCK] Would run: {' '.join(cmd)}[/dim]")
            return True
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗[/red] Error configuring GPU for {vmid}: {e.stderr}")
            return False

    def _add_mount(self, vmid: int, mount: Dict) -> bool:
        """Add mount point to container."""
        source = mount.get('source')
        target = mount.get('target')
        readonly = mount.get('readonly', False)
        
        if not source or not target:
            return False
        
        mp_id = 0  # Simplified
        ro_flag = ',ro=1' if readonly else ''
        mount_spec = f'{source},mp={target}{ro_flag}'
        
        cmd = ['pct', 'set', str(vmid), f'--mp{mp_id}', mount_spec]
        
        if self.mock:
            console.print(f"[dim][MOCK] Would run: {' '.join(cmd)}[/dim]")
            return True
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _get_next_vmid(self) -> int:
        """Get next available VMID."""
        return 100  # Simplified
