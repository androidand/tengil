"""Container lifecycle management (create, start, stop)."""
import subprocess
from typing import Dict, List, Optional

from tengil.core.logger import get_logger
from .templates import TemplateManager
from .discovery import ContainerDiscovery

logger = get_logger(__name__)


class ContainerLifecycle:
    """Manages LXC container lifecycle operations."""

    def __init__(self, mock: bool = False):
        self.mock = mock
        self.templates = TemplateManager(mock=mock)
        self.discovery = ContainerDiscovery(mock=mock)

    def create_container(self, spec: Dict, storage: str = 'local-lvm') -> Optional[int]:
        """Create a new LXC container.

        Args:
            spec: Container specification dict with:
                - name: Container hostname
                - vmid: Container ID (optional, will find next free if not provided)
                - template: Template name (e.g., 'debian-12-standard')
                - resources: Resource allocation (memory, cores, disk)
                - network: Network configuration (bridge, ip, gateway)
            storage: Storage location for container rootfs

        Returns:
            Container VMID if successful, None if failed
        """
        # Validate template is specified (required)
        template = spec.get('template')
        if not template:
            logger.error("Container template not specified in spec")
            return None

        # Ensure template is available (download if needed)
        if not self.templates.ensure_template_available(template):
            logger.error(f"Template {template} not available and download failed")
            return None

        if self.mock:
            vmid = spec.get('vmid', 200)
            name = spec.get('name', 'mock-container')
            logger.info(f"MOCK: Would create container {vmid} ({name})")
            return vmid

        # Get or assign VMID
        vmid = spec.get('vmid')
        if not vmid:
            vmid = self._get_next_free_vmid()
            logger.info(f"Auto-assigned VMID: {vmid}")

        # Check if container already exists
        if self.discovery.container_exists(vmid):
            logger.warning(f"Container {vmid} already exists, skipping creation")
            return vmid

        # Extract configuration
        name = spec.get('name', f'ct{vmid}')

        # Handle template file extension - user might provide full name or base name
        template_file = template if '.tar' in template else f'{template}.tar.zst'

        # Build pct create command
        cmd = [
            'pct', 'create', str(vmid),
            f'{storage}:vztmpl/{template_file}',
            f'--hostname', name,
        ]

        # Add resources
        resources = spec.get('resources', {})
        memory = resources.get('memory', 512)
        cores = resources.get('cores', 1)
        disk = resources.get('disk', '8G')
        swap = resources.get('swap', 512)

        cmd.extend([
            '--memory', str(memory),
            '--cores', str(cores),
            '--rootfs', f'{storage}:{disk}',
            '--swap', str(swap),
        ])

        # Add network configuration
        network = spec.get('network', {})
        bridge = network.get('bridge', 'vmbr0')
        ip = network.get('ip', 'dhcp')
        gateway = network.get('gateway')
        firewall = '1' if network.get('firewall', True) else '0'

        # Validate static IP format
        if ip != 'dhcp' and '/' not in ip:
            logger.warning(f"Static IP '{ip}' should include CIDR notation (e.g., '{ip}/24')")

        net_config = f'name=eth0,bridge={bridge},firewall={firewall}'
        if ip != 'dhcp':
            net_config += f',ip={ip}'
            if gateway:
                net_config += f',gw={gateway}'
        else:
            net_config += ',ip=dhcp'

        cmd.extend(['--net0', net_config])

        # Additional options
        cmd.extend([
            '--unprivileged', '1',
            '--onboot', '1',
            '--features', 'nesting=1',
        ])

        # GPU passthrough if requested
        gpu_config = spec.get('gpu', {})
        if gpu_config and gpu_config.get('passthrough', False):
            gpu_type = gpu_config.get('type', 'auto')
            
            if gpu_type == 'auto':
                # Auto-detect GPU type
                from tengil.discovery.hwdetect import SystemDetector
                detector = SystemDetector()
                gpus = detector._detect_gpu()
                
                if gpus:
                    gpu_type = gpus[0]['type']  # Use first detected GPU
                    logger.info(f"Auto-detected GPU: {gpu_type} - {gpus[0]['model']}")
                else:
                    logger.warning("GPU passthrough requested but no GPU detected")
                    gpu_type = None
            
            # Configure GPU passthrough based on type
            if gpu_type in ['intel', 'amd']:
                # Intel/AMD: Mount /dev/dri for hardware transcoding
                logger.info(f"Configuring {gpu_type} GPU passthrough via /dev/dri")
                # Note: /dev/dri mount will be added via lxc.cgroup2.devices.allow
                # This requires privileged container or manual config post-creation
                # For now, log a note about manual configuration needed
                logger.warning(f"  GPU passthrough requires manual configuration:")
                logger.warning(f"  1. Edit /etc/pve/lxc/{vmid}.conf")
                logger.warning(f"  2. Add: lxc.cgroup2.devices.allow: c 226:* rwm")
                logger.warning(f"  3. Add: lxc.mount.entry: /dev/dri dev/dri none bind,optional,create=dir")
                logger.warning(f"  Or use privileged container with --unprivileged 0")
                
            elif gpu_type == 'nvidia':
                # NVIDIA: Requires nvidia-container-runtime and different setup
                logger.info("Configuring NVIDIA GPU passthrough")
                logger.warning("  NVIDIA GPU passthrough requires:")
                logger.warning("  1. nvidia-container-runtime installed on host")
                logger.warning("  2. Manual LXC config modification")
                logger.warning("  3. See: https://github.com/NVIDIA/nvidia-container-toolkit")

        try:
            logger.info(f"Creating container {vmid} ({name}) with template {template}")
            logger.debug(f"Command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            logger.info(f"✓ Container {vmid} ({name}) created successfully")
            return vmid

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create container {vmid}: {e}")
            if e.stderr:
                logger.error(f"Error output: {e.stderr}")
            return None

    def _get_next_free_vmid(self, start: int = 100) -> int:
        """Find the next available VMID.

        Args:
            start: Starting VMID to check from

        Returns:
            Next available VMID
        """
        containers = self.discovery.list_containers()
        used_vmids = {c['vmid'] for c in containers}

        vmid = start
        while vmid in used_vmids:
            vmid += 1
            if vmid > 999999:  # Proxmox max
                raise ValueError("No free VMIDs available")

        return vmid

    def start_container(self, vmid: int) -> bool:
        """Start a container.

        Args:
            vmid: Container ID to start

        Returns:
            True if started successfully
        """
        if self.mock:
            logger.info(f"MOCK: Would start container {vmid}")
            return True

        try:
            logger.info(f"Starting container {vmid}")
            subprocess.run(
                ['pct', 'start', str(vmid)],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"✓ Container {vmid} started")
            return True

        except subprocess.CalledProcessError as e:
            # Container might already be running
            if e.stderr and 'already running' in e.stderr.lower():
                logger.info(f"Container {vmid} already running")
                return True
            logger.error(f"Failed to start container {vmid}: {e}")
            return False

    def stop_container(self, vmid: int) -> bool:
        """Stop a container.

        Args:
            vmid: Container ID to stop

        Returns:
            True if stopped successfully
        """
        if self.mock:
            logger.info(f"MOCK: Would stop container {vmid}")
            return True

        try:
            logger.info(f"Stopping container {vmid}")
            subprocess.run(
                ['pct', 'stop', str(vmid)],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"✓ Container {vmid} stopped")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop container {vmid}: {e}")
            return False

    def container_exists(self, vmid: int) -> bool:
        """Check if a container exists (delegates to discovery).

        Args:
            vmid: Container ID

        Returns:
            True if container exists
        """
        return self.discovery.container_exists(vmid)
