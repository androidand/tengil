"""High-level container orchestration (combines lifecycle, mounts, discovery)."""
import subprocess
from typing import Dict, List, Tuple, Optional

from tengil.core.logger import get_logger
from .lifecycle import ContainerLifecycle
from .mounts import MountManager
from .discovery import ContainerDiscovery
from .templates import TemplateManager
from tengil.services.post_install import PostInstallManager
from tengil.services.proxmox.backends.oci import OCIBackend
from tengil.services.proxmox.backends.lxc import LXCBackend

logger = get_logger(__name__)


class ContainerOrchestrator:
    """Orchestrates container operations (facade for all container subsystems)."""

    def __init__(self, mock: bool = False, permission_manager=None):
        self.mock = mock
        self.permission_manager = permission_manager
        self.lifecycle = ContainerLifecycle(mock=mock)
        self.mounts = MountManager(mock=mock, permission_manager=permission_manager)
        self.discovery = ContainerDiscovery(mock=mock)
        self.templates = TemplateManager(mock=mock)
        self.post_install = PostInstallManager(mock=mock)
        
        # Backend instances for OCI and LXC
        self.oci_backend = OCIBackend(mock=mock)
        self.lxc_backend = LXCBackend(mock=mock)

    # ==================== Delegation Methods ====================
    # Delegate to subsystems for backward compatibility

    # Lifecycle operations
    def create_container(self, spec, storage='local-lvm', pool: Optional[str] = None):
        """Create a new container (OCI or LXC based on spec).
        
        Auto-detects container type from spec:
        - If spec contains 'type: oci' or 'oci' section -> use OCI backend
        - Otherwise -> use traditional LXC backend
        
        Args:
            spec: Container specification dict
            storage: Storage backend for rootfs (default: local-lvm)
            pool: Resource pool name (optional)
            
        Returns:
            Container VMID if successful, None if failed
        """
        # Detect backend type from spec
        container_type = spec.get('type', '').lower()
        has_oci_section = 'oci' in spec
        
        if container_type == 'oci' or has_oci_section:
            # Use OCI backend
            logger.info("Detected OCI container spec, using OCI backend")
            return self._create_oci_container(spec, storage, pool)
        else:
            # Use traditional LXC backend
            return self.lifecycle.create_container(spec, storage, pool=pool)
    
    def _create_oci_container(self, spec, storage='local-lvm', pool: Optional[str] = None):
        """Create OCI container using OCIBackend.
        
        Args:
            spec: Container specification with 'oci' section
            storage: Storage backend for rootfs
            pool: Resource pool name (optional)
            
        Returns:
            Container VMID if successful, None if failed
        """
        oci_config = spec.get('oci', {})
        
        # Extract OCI image details
        image = oci_config.get('image')
        tag = oci_config.get('tag', 'latest')
        registry = oci_config.get('registry')
        
        if not image:
            logger.error("OCI spec missing required 'image' field")
            return None
        
        # Pull image if not already cached
        logger.info(f"Pulling OCI image: {image}:{tag}")
        template_ref = self.oci_backend.pull_image(image, tag, registry)
        
        if not template_ref:
            logger.error(f"Failed to pull OCI image: {image}:{tag}")
            return None
        
        logger.info(f"Image cached as: {template_ref}")
        
        # Create container using OCI backend
        vmid = self.oci_backend.create_container(
            spec=spec,
            template=template_ref,
            storage=storage,
            pool=pool
        )
        
        return vmid

    def start_container(self, vmid):
        """Start a container (delegates to lifecycle)."""
        return self.lifecycle.start_container(vmid)

    def stop_container(self, vmid):
        """Stop a container (delegates to lifecycle)."""
        return self.lifecycle.stop_container(vmid)

    def restart_container(self, vmid):
        """Restart a container (delegates to lifecycle)."""
        return self.lifecycle.restart_container(vmid)

    def exec_container_command(self, vmid: int, command: List[str], user: Optional[str] = None,
                               env: Optional[Dict[str, str]] = None, workdir: Optional[str] = None) -> int:
        """Execute command inside container via pct exec."""
        return self.lifecycle.exec_container_command(
            vmid,
            command,
            user=user,
            env=env,
            workdir=workdir,
        )

    def shell_container(self, vmid: int, user: Optional[str] = None) -> int:
        """Open interactive shell inside container via pct enter."""
        return self.lifecycle.enter_container_shell(vmid, user=user)

    def container_exists(self, vmid):
        """Check if container exists (delegates to discovery)."""
        return self.discovery.container_exists(vmid)

    # Discovery operations
    def list_containers(self):
        """List all containers (delegates to discovery)."""
        return self.discovery.list_containers()

    def find_container_by_name(self, name):
        """Find container by name (delegates to discovery)."""
        return self.discovery.find_container_by_name(name)

    def get_container_info(self, vmid):
        """Get container info (delegates to discovery)."""
        return self.discovery.get_container_info(vmid)

    def get_container_by_name(self, name):
        """Get container by name (delegates to discovery)."""
        return self.discovery.get_container_by_name(name)

    def get_all_containers_info(self):
        """Get all containers info (delegates to discovery)."""
        return self.discovery.get_all_containers_info()

    def get_container_config(self, vmid):
        """Get container config (delegates to discovery)."""
        return self.discovery.get_container_config(vmid)

    # Mount operations
    def get_container_mounts(self, vmid):
        """Get container mounts (delegates to mounts)."""
        return self.mounts.get_container_mounts(vmid)

    def add_container_mount(self, vmid, mount_point, host_path, container_path, readonly=False, container_name=None):
        """Add container mount (delegates to mounts)."""
        return self.mounts.add_container_mount(vmid, mount_point, host_path, container_path, readonly, container_name)

    def remove_container_mount(self, vmid, mount_point):
        """Remove container mount (delegates to mounts)."""
        return self.mounts.remove_container_mount(vmid, mount_point)

    def container_has_mount(self, vmid, host_path):
        """Check if container has mount (delegates to mounts)."""
        return self.mounts.container_has_mount(vmid, host_path)

    def get_next_free_mountpoint(self, vmid):
        """Get next free mountpoint (delegates to mounts)."""
        return self.mounts.get_next_free_mountpoint(vmid)

    # Template operations
    def list_available_templates(self):
        """List available templates (delegates to templates)."""
        return self.templates.list_available_templates()

    def template_exists_locally(self, template):
        """Check if template exists locally (delegates to templates)."""
        return self.templates.template_exists_locally(template)

    def download_template(self, template):
        """Download template (delegates to templates)."""
        return self.templates.download_template(template)

    def ensure_template_available(self, template):
        """Ensure template available (delegates to templates)."""
        return self.templates.ensure_template_available(template)

    # ==================== Orchestration Methods ====================

    def setup_container_mounts(self, dataset_name: str, dataset_config: Dict,
                             pool: str = 'tank') -> List[Tuple[int, bool, str]]:
        """Set up all container mounts for a dataset.

        Handles containers intelligently:
        - Creates containers if auto_create=true (Phase 2)
        - Looks up existing containers by vmid or name
        - Checks if mount already exists (idempotent)
        - Only adds mount if container exists and mount is new

        Args:
            dataset_name: Name of the dataset
            dataset_config: Dataset configuration dict
            pool: ZFS pool name

        Returns:
            List of (vmid, success, message) tuples
        """
        results = []

        # Check if containers are configured
        containers = dataset_config.get('containers', [])
        if not containers:
            return results

        # Host path for the dataset
        host_path = f"/{pool}/{dataset_name}"

        for idx, container_spec in enumerate(containers):
            was_created = False
            auto_create = False
            # Parse container specification
            if isinstance(container_spec, dict):
                vmid = container_spec.get('vmid')
                container_name = container_spec.get('name')
                mount_path = container_spec.get('mount', f"/{dataset_name}")
                readonly = container_spec.get('readonly', False)
                auto_create = container_spec.get('auto_create', False)

                # Phase 2: Create container if auto_create is enabled
                if auto_create:
                    # Check if OCI container - need to pull image first
                    is_oci = container_spec.get('type') == 'oci'
                    template = container_spec.get('template')
                    
                    if is_oci and container_spec.get('image'):
                        # Pull OCI image and get template reference
                        image = container_spec.get('image')
                        tag = 'latest'  # Default tag
                        if ':' in image:
                            image, tag = image.rsplit(':', 1)
                        
                        logger.info(f"Pulling OCI image: {image}:{tag}")
                        template_ref = self.oci_backend.pull_image(image, tag)
                        if not template_ref:
                            msg = f"Container '{container_name or vmid}': failed to pull OCI image {image}:{tag}"
                            logger.error(msg)
                            results.append((0, False, "image pull failed"))
                            continue
                        # Extract just the filename from 'local:vztmpl/filename.tar'
                        template = template_ref.split('/')[-1]
                        # Store template for create_container call
                        container_spec['template'] = template
                    elif not template:
                        msg = f"Container '{container_name or vmid}': auto_create requires 'template' field (LXC) or 'image' field (OCI)"
                        logger.error(msg)
                        results.append((0, False, "missing template/image"))
                        continue

                    # Check if container already exists
                    existing_vmid = None
                    if vmid and self.discovery.container_exists(vmid):
                        existing_vmid = vmid
                        logger.info(f"Container {vmid} ({container_name}) already exists")
                    elif container_name:
                        existing_vmid = self.discovery.find_container_by_name(container_name)
                        if existing_vmid:
                            logger.info(f"Container '{container_name}' already exists (vmid={existing_vmid})")

                    if not existing_vmid:
                        # Create new container
                        logger.info(f"Creating container '{container_name}' from template {template}")
                        # Use pool name from container spec, fallback to tank then local-zfs
                        # TODO: Pass pool name through dataset context instead of via container spec
                        storage = container_spec.get('_pool_name') or container_spec.get('pool', 'tank')
                        created_vmid = self.lifecycle.create_container(
                            container_spec,
                            storage=storage,
                            pool=container_spec.get('pool'),
                            template_storage='local'  # Templates are always in 'local' storage
                        )

                        if not created_vmid:
                            msg = f"Failed to create container '{container_name}'"
                            logger.error(msg)
                            results.append((0, False, "creation failed"))
                            continue

                        logger.info(f"✓ Created container '{container_name}' (vmid={created_vmid})")
                        was_created = True

                        # Start container
                        if self.lifecycle.start_container(created_vmid):
                            logger.info(f"✓ Started container {created_vmid}")
                            
                            # Run post-install if specified
                            post_install = container_spec.get('post_install')
                            if post_install:
                                logger.info(f"Running post-install tasks for container {created_vmid}...")

                                # Wait for container to boot
                                if self.post_install.wait_for_container_boot(created_vmid, timeout=30):
                                    if self.post_install.run_post_install(created_vmid, post_install):
                                        logger.info(f"✓ Post-install completed for container {created_vmid}")
                                        
                                        # Show container IP and service URLs
                                        self._display_container_access_info(created_vmid, container_name, post_install)
                                    else:
                                        msg = f"Post-install failed for container {created_vmid}"
                                        logger.error(msg)
                                        results.append((created_vmid, False, "post-install failed"))
                                        continue
                                else:
                                    msg = f"Container {created_vmid} boot timeout, post-install cannot run"
                                    logger.error(msg)
                                    results.append((created_vmid, False, "boot timeout"))
                                    continue
                            else:
                                # Show IP even without post-install
                                self._display_container_access_info(created_vmid, container_name, None)
                        else:
                            logger.warning(f"Container {created_vmid} created but failed to start")

                        vmid = created_vmid
                    else:
                        # Use existing container
                        vmid = existing_vmid

                    # Update container_name for logging if not set
                    if not container_name:
                        info = self.discovery.get_container_info(vmid)
                        container_name = info['name'] if info else f"CT{vmid}"

            elif isinstance(container_spec, str):
                # Simple format: "container_name:/mount/path" or "container_name:/mount/path:ro"
                parts = container_spec.split(':')
                container_name = parts[0]
                mount_path = parts[1] if len(parts) > 1 else f"/{dataset_name}"
                readonly = (len(parts) > 2 and parts[2] == 'ro')
                vmid = None

            else:
                logger.warning(f"Invalid container spec: {container_spec}")
                results.append((0, False, "invalid spec format"))
                continue

            # Find container VMID (try vmid first, then name)
            if vmid:
                # vmid provided, verify it exists
                if not self.discovery.container_exists(vmid):
                    msg = f"Container {vmid} not found"
                    logger.warning(f"{msg} - skipping mount")
                    logger.info(f"  Create the container first, then re-run 'tg apply'")
                    results.append((vmid, False, msg))
                    continue
                # Get name for logging
                info = self.discovery.get_container_info(vmid)
                info_name = info['name'] if info else None
                if container_name and info_name and container_name != info_name:
                    msg = (
                        f"Container name mismatch for vmid {vmid}: "
                        f"expected '{container_name}', found '{info_name}'"
                    )
                    logger.error(f"{msg} - skipping mount to avoid wrong target")
                    results.append((vmid, False, "name mismatch"))
                    continue

                container_name = info_name or container_name or f"CT{vmid}"
            else:
                # Name provided, look up vmid
                vmid = self.discovery.find_container_by_name(container_name)
                if not vmid:
                    msg = f"Container '{container_name}' not found"
                    logger.warning(f"{msg} - skipping mount")
                    logger.info(f"  Create the container first, then re-run 'tg apply'")
                    results.append((0, False, msg))
                    continue

            # Check if mount already exists (idempotent)
            if self.mounts.container_has_mount(vmid, host_path):
                msg = f"Mount already exists: {host_path} → {container_name}:{mount_path}"
                logger.info(f"✓ {msg}")
                # Apply env if requested even when mount already exists
                self._apply_env(vmid, container_spec, container_name)
                results.append((vmid, True, "already exists"))
                continue

            # Find next available mount point
            try:
                mp_num = self.mounts.get_next_free_mountpoint(vmid)
            except ValueError as e:
                msg = f"No free mount points for container {vmid}"
                logger.error(f"{msg}: {e}")
                results.append((vmid, False, msg))
                continue

            # Add the mount
            success = self.mounts.add_container_mount(
                vmid=vmid,
                mount_point=mp_num,
                host_path=host_path,
                container_path=mount_path,
                readonly=readonly,
                container_name=container_name
            )

            if success:
                msg = f"Mounted {host_path} → {container_name}:{mount_path}"
                if auto_create and was_created:
                    results.append((vmid, True, "created and mounted"))
                else:
                    results.append((vmid, True, "mounted"))
                logger.info(f"✓ {msg}")
                # Apply env after mount succeeds
                self._apply_env(vmid, container_spec, container_name)
            else:
                msg = f"Failed to mount {host_path} → {container_name}"
                logger.error(msg)
                results.append((vmid, False, "mount failed"))

        return results

    def _apply_env(self, vmid: int, container_spec: Dict, container_name: Optional[str] = None) -> bool:
        """Ensure container env matches spec, restarting if running."""
        if not isinstance(container_spec, dict):
            return True
        env = container_spec.get('env') or container_spec.get('oci', {}).get('env') or {}
        if not env:
            return True

        is_oci = container_spec.get('type') == 'oci' or 'oci' in container_spec
        updater = self.oci_backend.update_env if is_oci else self.lxc_backend.update_env

        if not updater(vmid, env):
            logger.error(f"Failed to apply env to container {vmid}")
            return False

        # Restart if running to apply env
        info = self.discovery.get_container_info(vmid)
        status = info.get('status') if info else None
        if status == 'running':
            self.lifecycle.restart_container(vmid)
        return True
    
    def _display_container_access_info(self, vmid: int, container_name: str, post_install: list = None):
        """Display container IP address and access information.
        
        Args:
            vmid: Container ID
            container_name: Container name
            post_install: List of post-install tasks (to detect services)
        """
        try:
            # Get container IP
            result = subprocess.run(
                ['pct', 'exec', str(vmid), '--', 'hostname', '-I'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                ip = result.stdout.strip().split()[0]  # First IP if multiple
                
                logger.info("=" * 60)
                logger.info(f"🎉 Container '{container_name}' (ID {vmid}) is ready!")
                logger.info(f"   IP Address: {ip}")
                
                # Show service URLs if we know what was installed
                if post_install:
                    if 'portainer' in post_install or 'tteck/portainer' in post_install:
                        logger.info(f"   Portainer:  http://{ip}:9000")
                    if 'jellyfin' in post_install or 'tteck/jellyfin' in post_install:
                        logger.info(f"   Jellyfin:   http://{ip}:8096")
                    if 'homeassistant' in post_install or 'tteck/homeassistant' in post_install:
                        logger.info(f"   Home Assistant: http://{ip}:8123")
                    if 'nextcloud' in post_install or 'tteck/nextcloud' in post_install:
                        logger.info(f"   Nextcloud:  http://{ip}")
                    if 'pihole' in post_install or 'tteck/pihole' in post_install:
                        logger.info(f"   Pi-hole:    http://{ip}/admin")
                
                logger.info("=" * 60)
            else:
                logger.debug(f"Could not get IP for container {vmid}")
                
        except Exception as e:
            logger.debug(f"Could not display access info for container {vmid}: {e}")
