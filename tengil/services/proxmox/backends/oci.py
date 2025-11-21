"""OCI container backend using skopeo + Proxmox OCI support."""
import subprocess
import shlex
from pathlib import Path
from typing import Dict, Optional
from rich.console import Console
from .base import ContainerBackend

console = Console()


class OCIBackend(ContainerBackend):
    """OCI backend using skopeo for image pulling and pct for container management."""

    def __init__(self, node: str = 'localhost', mock: bool = False):
        """Initialize OCI backend.
        
        Args:
            node: Proxmox node name
            mock: If True, simulate operations
        """
        super().__init__(mock)
        self.node = node
        self.template_dir = Path('/var/lib/vz/template/cache')

    def pull_image(
        self,
        image: str,
        tag: str = 'latest',
        registry: Optional[str] = None
    ) -> Optional[str]:
        """Pull OCI image using skopeo.
        
        Args:
            image: Image name (e.g., 'jellyfin/jellyfin' or 'ghcr.io/owner/image')
            tag: Image tag (default: 'latest')
            registry: Registry URL (default: Docker Hub, ignored if image contains registry)
            
        Returns:
            Template reference (e.g., 'local:vztmpl/jellyfin-latest.tar') or None if failed
        """
        # Check if image already contains a registry (has domain-like prefix)
        if '/' in image and '.' in image.split('/')[0]:
            # Image already has registry (e.g., ghcr.io/owner/image)
            source = f'docker://{image}:{tag}'
        else:
            # Use provided registry or default to Docker Hub
            if not registry:
                registry = 'docker.io'
            source = f'docker://{registry}/{image}:{tag}'
        
        # Generate filename
        image_name = image.split('/')[-1]
        filename = f'{image_name}-{tag}.tar'
        dest_path = self.template_dir / filename
        dest = f'oci-archive:{dest_path}'
        
        # Build skopeo command
        cmd = ['skopeo', 'copy', source, dest]
        
        if self.mock:
            console.print(f"[dim][MOCK] Would run: {' '.join(cmd)}[/dim]")
            return f'local:vztmpl/{filename}'
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return f'local:vztmpl/{filename}'
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗[/red] Error pulling image: {e.stderr}")
            return None

    def create_container(
        self,
        spec: Dict,
        storage: str = 'local-zfs',
        pool: Optional[str] = None,
        template: Optional[str] = None,
        **kwargs
    ) -> Optional[int]:
        """Create OCI container.
        
        Args:
            spec: Container specification with 'oci' section
            storage: Storage backend for rootfs
            pool: Resource pool (optional)
            template: Optional pre-pulled template reference (local:vztmpl/...)
            **kwargs: Additional options
            
        Returns:
            Container VMID or None if failed
        """
        oci_spec = spec.get('oci', {})

        # Validate mounts early (avoid pulling if spec is invalid)
        mounts = spec.get('mounts', [])
        for mount in mounts:
            if not mount.get('source') or not mount.get('target'):
                console.print(f"[red]✗[/red] Invalid mount spec (source/target required): {mount}")
                return None

        # Pull image if needed (unless template supplied)
        template_ref = template  # may be passed in by orchestrator
        if not template_ref:
            image = oci_spec.get('image')
            tag = oci_spec.get('tag', 'latest')
            registry = oci_spec.get('registry')
            
            if not image:
                console.print("[red]✗[/red] No image specified in oci section")
                return None
            
            # Check if template exists or pull it
            image_name = image.split('/')[-1]
            template_name = f'{image_name}-{tag}.tar'
            template_path = self.template_dir / template_name
            
            if not template_path.exists():
                console.print(f"[cyan]→[/cyan] Pulling OCI image: {image}:{tag}")
                template_ref = self.pull_image(image, tag, registry)
                if not template_ref:
                    return None
            else:
                template_ref = f'local:vztmpl/{template_name}'
        
        # Get or allocate VMID
        vmid = spec.get('vmid') or self._get_next_vmid()
        
        # Build pct create command
        cmd = ['pct', 'create', str(vmid), template_ref]
        
        # Add basic options
        hostname = spec.get('hostname') or spec.get('name')
        if hostname:
            cmd.extend(['--hostname', hostname])
        
        # Resources (prefer top-level, fallback to resources section)
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
        net_parts = [f'name=eth0', f'bridge={bridge}']
        # firewall flag if provided
        if network.get('firewall') is not None:
            net_parts.append(f'firewall={int(bool(network.get("firewall")))}')
        if ip != 'dhcp':
            net_parts.append(f'ip={ip}')
            if network.get('gateway'):
                net_parts.append(f'gw={network["gateway"]}')
        else:
            net_parts.append('ip=dhcp')
        cmd.extend(['--net0', ','.join(net_parts)])
        
        # Unprivileged (default for OCI)
        if spec.get('unprivileged', True):
            cmd.extend(['--unprivileged', '1'])

        # Features
        features = spec.get('features', {})
        if features:
            feature_str = ','.join(f'{k}={int(v)}' for k, v in features.items() if v is not None)
            if feature_str:
                cmd.extend(['--features', feature_str])

        # Environment variables at create time (gap noted in Proxmox UI)
        env = spec.get('env') or oci_spec.get('env') or {}
        for key, value in env.items():
            cmd.extend(['--env', f'{key}={value}'])
        
        # Pool
        if pool:
            cmd.extend(['--pool', pool])
        
        # Execute creation
        if self.mock:
            console.print(f"[dim][MOCK] Would run: {' '.join(cmd)}[/dim]")
            return vmid
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Configure GPU if specified
            if spec.get('gpu', {}).get('passthrough') or features.get('gpu'):
                self.configure_gpu(vmid)
            
            # Add mounts
            mounts = spec.get('mounts', [])
            for mount in mounts:
                if not self._add_mount(vmid, mount):
                    console.print(f"[red]✗[/red] Error adding mount: {mount}")
                    return None
            
            return vmid
            
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗[/red] Error creating container: {e.stderr}")
            return None

    def start_container(self, vmid: int) -> bool:
        """Start OCI container."""
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
        """Stop OCI container."""
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
        """Destroy OCI container."""
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
        # Add Intel GPU devices (most common)
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
            console.print(f"[red]✗[/red] Invalid mount spec: {mount}")
            return False
        
        # Find next available mpX slot
        mp_id = self._get_next_mp_slot(vmid)
        ro_flag = ',ro=1' if readonly else ''
        mount_spec = f'{source},mp={target}{ro_flag}'
        
        cmd = ['pct', 'set', str(vmid), f'--mp{mp_id}', mount_spec]
        
        if self.mock:
            console.print(f"[dim][MOCK] Would run: {' '.join(cmd)}[/dim]")
            return True
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗[/red] Error adding mount {mount}: {e.stderr}")
            return False

    def _get_next_vmid(self) -> int:
        """Get next available VMID."""
        # Simple implementation: start at 200 for OCI containers
        # TODO: Query Proxmox for actual next VMID
        return 200

    def _get_next_mp_slot(self, vmid: int) -> int:
        """Get next available mount point slot."""
        if self.mock:
            return 0

        try:
            result = subprocess.run(
                ['pct', 'config', str(vmid)],
                capture_output=True,
                text=True,
                check=True
            )
            max_slot = -1
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith('mp') and ':' in line:
                    try:
                        slot = int(line.split(':', 1)[0][2:])
                        max_slot = max(max_slot, slot)
                    except ValueError:
                        continue
            return max_slot + 1
        except subprocess.CalledProcessError:
            return 0
