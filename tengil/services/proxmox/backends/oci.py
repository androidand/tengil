"""OCI container backend using skopeo + Proxmox OCI support."""
import subprocess
import shlex
from pathlib import Path
from typing import Dict, Optional
from .base import ContainerBackend


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
            image: Image name (e.g., 'jellyfin/jellyfin')
            tag: Image tag (default: 'latest')
            registry: Registry URL (default: Docker Hub)
            
        Returns:
            Template reference (e.g., 'local:vztmpl/jellyfin-latest.tar') or None if failed
        """
        # Default to Docker Hub
        if not registry:
            registry = 'docker.io'
        
        # Build full image reference
        source = f'docker://{registry}/{image}:{tag}'
        
        # Generate filename
        image_name = image.split('/')[-1]
        filename = f'{image_name}-{tag}.tar'
        dest_path = self.template_dir / filename
        dest = f'oci-archive:{dest_path}'
        
        # Build skopeo command
        cmd = ['skopeo', 'copy', source, dest]
        
        if self.mock:
            print(f"[MOCK] Would run: {' '.join(cmd)}")
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
            print(f"Error pulling image: {e.stderr}")
            return None

    def create_container(
        self,
        spec: Dict,
        storage: str = 'local-zfs',
        pool: Optional[str] = None,
        **kwargs
    ) -> Optional[int]:
        """Create OCI container.
        
        Args:
            spec: Container specification with 'oci' section
            storage: Storage backend for rootfs
            pool: Resource pool (optional)
            **kwargs: Additional options
            
        Returns:
            Container VMID or None if failed
        """
        oci_spec = spec.get('oci', {})
        
        # Pull image if needed
        image = oci_spec.get('image')
        tag = oci_spec.get('tag', 'latest')
        registry = oci_spec.get('registry')
        
        if not image:
            print("Error: No image specified in oci section")
            return None
        
        # Check if template exists or pull it
        image_name = image.split('/')[-1]
        template_name = f'{image_name}-{tag}.tar'
        template_path = self.template_dir / template_name
        
        if not template_path.exists():
            print(f"Pulling OCI image: {image}:{tag}")
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
        cmd.extend(['--net0', f'name=eth0,bridge={bridge},ip={ip}'])
        
        # Unprivileged (default for OCI)
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
        
        # Execute creation
        if self.mock:
            print(f"[MOCK] Would run: {' '.join(cmd)}")
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
                self._add_mount(vmid, mount)
            
            return vmid
            
        except subprocess.CalledProcessError as e:
            print(f"Error creating container: {e.stderr}")
            return None

    def start_container(self, vmid: int) -> bool:
        """Start OCI container."""
        cmd = ['pct', 'start', str(vmid)]
        
        if self.mock:
            print(f"[MOCK] Would run: {' '.join(cmd)}")
            return True
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error starting container {vmid}: {e.stderr}")
            return False

    def stop_container(self, vmid: int, timeout: int = 30) -> bool:
        """Stop OCI container."""
        cmd = ['pct', 'stop', str(vmid), '--timeout', str(timeout)]
        
        if self.mock:
            print(f"[MOCK] Would run: {' '.join(cmd)}")
            return True
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error stopping container {vmid}: {e.stderr}")
            return False

    def destroy_container(self, vmid: int, purge: bool = False) -> bool:
        """Destroy OCI container."""
        cmd = ['pct', 'destroy', str(vmid)]
        if purge:
            cmd.append('--purge')
        
        if self.mock:
            print(f"[MOCK] Would run: {' '.join(cmd)}")
            return True
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error destroying container {vmid}: {e.stderr}")
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
            print(f"[MOCK] Would run: {' '.join(cmd)}")
            return True
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error configuring GPU for {vmid}: {e.stderr}")
            return False

    def _add_mount(self, vmid: int, mount: Dict) -> bool:
        """Add mount point to container."""
        source = mount.get('source')
        target = mount.get('target')
        readonly = mount.get('readonly', False)
        
        if not source or not target:
            print(f"Invalid mount spec: {mount}")
            return False
        
        # Find next available mpX slot
        mp_id = self._get_next_mp_slot(vmid)
        ro_flag = ',ro=1' if readonly else ''
        mount_spec = f'{source},mp={target}{ro_flag}'
        
        cmd = ['pct', 'set', str(vmid), f'--mp{mp_id}', mount_spec]
        
        if self.mock:
            print(f"[MOCK] Would run: {' '.join(cmd)}")
            return True
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error adding mount {mount}: {e.stderr}")
            return False

    def _get_next_vmid(self) -> int:
        """Get next available VMID."""
        # Simple implementation: start at 200 for OCI containers
        # TODO: Query Proxmox for actual next VMID
        return 200

    def _get_next_mp_slot(self, vmid: int) -> int:
        """Get next available mount point slot."""
        # Simple implementation: return 0 (first slot)
        # TODO: Parse pct config to find next available slot
        return 0
