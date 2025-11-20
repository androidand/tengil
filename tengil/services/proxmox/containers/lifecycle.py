"""Container lifecycle management (create, start, stop)."""
import shlex
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

    def create_container(
        self,
        spec: Dict,
        storage: str = 'local-lvm',
        pool: Optional[str] = None,
        template_storage: str = 'local'
    ) -> Optional[int]:
        """Create a new LXC container.

        Args:
            spec: Container specification dict with:
                - name: Container hostname
                - vmid: Container ID (optional, will find next free if not provided)
                - template: Template name (e.g., 'debian-12-standard')
                - resources: Resource allocation (memory, cores, disk)
                - network: Network configuration (bridge, ip, gateway)
            storage: Storage backend for rootfs (default: local-lvm)
            pool: Resource pool name (optional)
            template_storage: Storage backend where templates are stored (default: local)
            storage: Storage location for container rootfs

        Returns:
            Container VMID if successful, None if failed
        """
        pool = pool if pool is not None else spec.get('pool')

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
        # Template is always from template_storage (usually 'local'), rootfs goes to storage
        cmd = [
            'pct', 'create', str(vmid),
            f'{template_storage}:vztmpl/{template_file}',
            f'--hostname', name,
        ]

        # Add resources
        resources = spec.get('resources', {})
        memory = resources.get('memory', 512)
        cores = resources.get('cores', 1)
        disk = resources.get('disk', '8G')
        swap = resources.get('swap', 512)

        # For ZFS storage, Proxmox expects size as a number (in GB) without unit suffix
        # Convert '128G' -> '128', '8G' -> '8', etc.
        disk_size = str(disk).rstrip('GgMmKkTt') if isinstance(disk, str) else str(disk)

        cmd.extend([
            '--memory', str(memory),
            '--cores', str(cores),
            '--rootfs', f'{storage}:{disk_size}',
            '--swap', str(swap),
        ])

        # Add resource pool if specified (explicit parameter > resources > spec)
        resource_pool = resources.get('pool')
        selected_pool = pool
        if resource_pool:
            selected_pool = resource_pool
        if selected_pool:
            cmd.extend(['--pool', selected_pool])
            logger.info(f"Assigning container to resource pool: {selected_pool}")

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

        description = spec.get('description')
        if description:
            cmd.extend(['--description', description])

        tags = spec.get('tags')
        if tags:
            if isinstance(tags, str):
                tags_value = tags
            else:
                tags_value = ",".join(tag.strip() for tag in tags if tag)
            if tags_value:
                cmd.extend(['--tags', tags_value])
        
        startup_value = spec.get('startup')
        if not startup_value:
            startup_parts = []
            if spec.get('startup_order') is not None:
                startup_parts.append(f"order={spec['startup_order']}")
            if spec.get('startup_delay') is not None:
                startup_parts.append(f"up={spec['startup_delay']}")
            if startup_parts:
                startup_value = ",".join(startup_parts)
        if startup_value:
            cmd.extend(['--startup', startup_value])

        # Privileged vs unprivileged (default: unprivileged for security)
        # Note: In newer Proxmox, containers default to unprivileged, must explicitly set --unprivileged 0
        privileged = spec.get('privileged', False)
        if privileged:
            # Explicitly request privileged container
            cmd.extend(['--unprivileged', '0'])
            logger.warning(f"⚠️  Creating PRIVILEGED container {vmid} - has full root access!")
        else:
            cmd.extend(['--unprivileged', '1'])

        # Additional options
        cmd.extend([
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
            
            # Store GPU info for post-creation config
            if gpu_type:
                spec['_gpu_type'] = gpu_type

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
            
            # Handle requires_docker flag for automatic Docker support
            if spec.get('requires_docker', False):
                self._configure_docker_support(vmid)
            
            # Handle GPU passthrough configuration
            if spec.get('_gpu_type'):
                self._configure_gpu_passthrough(vmid, spec['_gpu_type'])
            
            return vmid

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create container {vmid}: {e}")
            if e.stderr:
                logger.error(f"Error output: {e.stderr}")
            return None

    def _configure_docker_support(self, vmid: int) -> bool:
        """Configure container for Docker support.
        
        Adds AppArmor profile unconfined and keyctl feature to enable Docker.
        
        Args:
            vmid: Container ID to configure
            
        Returns:
            True if configured successfully
        """
        config_path = f"/etc/pve/lxc/{vmid}.conf"
        
        try:
            logger.info(f"Configuring Docker support for container {vmid}")
            
            # Read current config
            with open(config_path, 'r') as f:
                config_lines = f.readlines()
            
            # Check if already configured
            has_apparmor = any('lxc.apparmor.profile' in line for line in config_lines)
            has_keyctl = any('keyctl=1' in line for line in config_lines)
            
            modified = False
            
            # Add AppArmor profile if not present
            if not has_apparmor:
                config_lines.append('lxc.apparmor.profile: unconfined\n')
                logger.info(f"  ✓ Added AppArmor unconfined profile")
                modified = True
            
            # Add keyctl to features if not present
            if not has_keyctl:
                # Find features line and update it
                for i, line in enumerate(config_lines):
                    if line.startswith('features:'):
                        # Add keyctl to existing features
                        config_lines[i] = line.rstrip() + ',keyctl=1\n'
                        logger.info(f"  ✓ Added keyctl=1 to features")
                        modified = True
                        break
            
            # Write back if modified
            if modified:
                with open(config_path, 'w') as f:
                    f.writelines(config_lines)
                logger.info(f"✓ Docker support configured for container {vmid}")
            else:
                logger.info(f"  Docker support already configured for container {vmid}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure Docker support for container {vmid}: {e}")
            return False

    def _configure_gpu_passthrough(self, vmid: int, gpu_type: str) -> bool:
        """Configure container for GPU passthrough.
        
        Adds device access and mount configuration for /dev/dri (Intel/AMD GPU).
        
        Args:
            vmid: Container ID to configure
            gpu_type: GPU type ('intel', 'amd', or 'nvidia')
            
        Returns:
            True if configured successfully
        """
        config_path = f"/etc/pve/lxc/{vmid}.conf"
        
        try:
            logger.info(f"Configuring {gpu_type} GPU passthrough for container {vmid}")
            
            if gpu_type in ['intel', 'amd']:
                # Read current config
                with open(config_path, 'r') as f:
                    config_lines = f.readlines()
                
                # Add GPU device access and mount
                # cgroup2 device allow for /dev/dri (char device 226:*)
                config_lines.append('lxc.cgroup2.devices.allow: c 226:* rwm\n')
                # Mount /dev/dri into container
                config_lines.append('lxc.mount.entry: /dev/dri dev/dri none bind,optional,create=dir\n')
                
                # Write back
                with open(config_path, 'w') as f:
                    f.writelines(config_lines)
                
                logger.info(f"  ✓ Added /dev/dri device access (c 226:* rwm)")
                logger.info(f"  ✓ Added /dev/dri mount binding")
                logger.info(f"✓ {gpu_type.upper()} GPU passthrough configured for container {vmid}")
                
            elif gpu_type == 'nvidia':
                logger.warning(f"  NVIDIA GPU passthrough requires nvidia-container-runtime")
                logger.warning(f"  Manual setup needed - see: https://github.com/NVIDIA/nvidia-container-toolkit")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure GPU passthrough for container {vmid}: {e}")
            return False

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

    def restart_container(self, vmid: int) -> bool:
        """Restart a container.

        Args:
            vmid: Container ID to restart

        Returns:
            True if restarted successfully
        """
        if self.mock:
            logger.info(f"MOCK: Would restart container {vmid}")
            return True

        try:
            logger.info(f"Restarting container {vmid}")
            subprocess.run(
                ['pct', 'restart', str(vmid)],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"✓ Container {vmid} restarted")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restart container {vmid}: {e}")
            if e.stderr:
                logger.error(f"Error output: {e.stderr}")
            return False

    def exec_container_command(
        self,
        vmid: int,
        command: List[str],
        user: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        workdir: Optional[str] = None,
    ) -> int:
        """Run a command inside the container using pct exec."""
        if not command:
            logger.error("No command provided for pct exec")
            return 1

        base_cmd: List[str] = ['pct', 'exec', str(vmid)]

        if user:
            base_cmd.extend(['--user', user])

        if workdir:
            base_cmd.extend(['--cwd', workdir])

        if env:
            for key, value in env.items():
                base_cmd.extend(['--env', f"{key}={value}"])

        base_cmd.append('--')
        base_cmd.extend(command)

        command_str = shlex.join(base_cmd)

        if self.mock:
            logger.info(f"MOCK: Would execute: {command_str}")
            return 0

        try:
            logger.info(f"Executing in container {vmid}: {command_str}")
            result = subprocess.run(base_cmd, check=False)
            if result.returncode != 0:
                logger.error(f"Command exited with code {result.returncode}")
            return result.returncode
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(f"Failed to execute in container {vmid}: {exc}")
            return 1

    def enter_container_shell(
        self,
        vmid: int,
        user: Optional[str] = None,
    ) -> int:
        """Open an interactive shell inside the container using pct enter."""
        base_cmd: List[str] = ['pct', 'enter', str(vmid)]

        if user:
            base_cmd.extend(['--user', user])

        command_str = shlex.join(base_cmd)

        if self.mock:
            logger.info(f"MOCK: Would open shell: {command_str}")
            return 0

        try:
            logger.info(f"Opening interactive shell for container {vmid}")
            result = subprocess.run(base_cmd, check=False)
            if result.returncode != 0:
                logger.error(f"Shell exited with code {result.returncode}")
            return result.returncode
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(f"Failed to open shell for container {vmid}: {exc}")
            return 1

    def container_exists(self, vmid: int) -> bool:
        """Check if a container exists (delegates to discovery).

        Args:
            vmid: Container ID

        Returns:
            True if container exists
        """
        return self.discovery.container_exists(vmid)

    def update_container(self, vmid: int, upgrade: bool = True) -> bool:
        """Update packages in a container (apt update && apt upgrade).

        Args:
            vmid: Container VMID
            upgrade: If True, run apt upgrade. If False, only apt update.

        Returns:
            True if update successful
        """
        if self.mock:
            logger.info(f"MOCK: Would update container {vmid}")
            return True

        logger.info(f"Updating container {vmid}...")

        # Build update command
        if upgrade:
            cmd = [
                'pct', 'exec', str(vmid), '--',
                'bash', '-c',
                'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y'
            ]
        else:
            cmd = ['pct', 'exec', str(vmid), '--', 'apt-get', 'update']

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"✓ Updated container {vmid}")
            if result.stdout:
                logger.debug(result.stdout)
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Failed to update container {vmid}: {e}")
            if e.stderr:
                logger.error(f"Error output: {e.stderr}")
            return False
