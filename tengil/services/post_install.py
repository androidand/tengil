"""Post-installation automation for LXC containers.

Integrates with existing tools:
- Docker/Portainer installation
- tteck Proxmox Helper Scripts
- Custom shell commands

Runs commands inside containers via `pct exec`.
"""
import subprocess
import time
from typing import List, Optional, Union
from tengil.core.logger import get_logger
from tengil.core.retry import retry
from tengil.core.config import get_config

logger = get_logger(__name__)


class PostInstallManager:
    """Manages post-installation tasks in LXC containers."""

    # tteck script base URL
    TTECK_BASE_URL = "https://raw.githubusercontent.com/tteck/Proxmox/main/install"
    
    # Known tteck scripts (subset of available ones)
    TTECK_SCRIPTS = {
        'jellyfin': 'jellyfin-install.sh',
        'immich': 'immich-install.sh',
        'homeassistant': 'home-assistant-install.sh',
        'nextcloud': 'nextcloud-install.sh',
        'pihole': 'pihole-install.sh',
        'adguard': 'adguard-install.sh',
        'wireguard': 'wireguard-install.sh',
        'portainer': 'portainer-install.sh',
        'docker': 'docker-install.sh',
        'nginx-proxy-manager': 'nginxproxymanager-install.sh',
        'plex': 'plex-install.sh',
        'sonarr': 'sonarr-install.sh',
        'radarr': 'radarr-install.sh',
        'lidarr': 'lidarr-install.sh',
        'qbittorrent': 'qbittorrent-install.sh',
        'transmission': 'transmission-install.sh',
    }

    def __init__(self, mock: bool = False):
        self.mock = mock

    def run_post_install(self, vmid: int, post_install: Union[str, List[str]]) -> bool:
        """Run post-install tasks for a container.
        
        Args:
            vmid: Container ID
            post_install: String or list of install tasks
                - 'docker': Install Docker
                - 'portainer': Install Portainer (requires docker)
                - 'tteck/<script>': Run tteck script
                - Custom shell commands (multiline string)
        
        Returns:
            True if all tasks completed successfully
        """
        # Normalize to list
        if isinstance(post_install, str):
            tasks = [post_install]
        else:
            tasks = post_install

        logger.info(f"Running post-install tasks for container {vmid}")
        
        for task in tasks:
            if not self._run_task(vmid, task):
                logger.error(f"Post-install task failed: {task}")
                return False
        
        logger.info(f"✓ All post-install tasks completed for container {vmid}")
        return True

    def _run_task(self, vmid: int, task: str) -> bool:
        """Run a single post-install task.
        
        Args:
            vmid: Container ID
            task: Task specification
        
        Returns:
            True if task completed successfully
        """
        task = task.strip()
        
        # Built-in installers
        if task == 'docker':
            return self.install_docker(vmid)
        elif task == 'portainer':
            return self.install_portainer(vmid)
        
        # tteck scripts
        elif task.startswith('tteck/'):
            script_name = task.split('/', 1)[1]
            return self.run_tteck_script(vmid, script_name)
        
        # Custom shell command
        else:
            return self.run_custom_command(vmid, task)

    def install_docker(self, vmid: int) -> bool:
        """Install Docker and Docker Compose in container.
        
        Uses official Docker installation method.
        
        Args:
            vmid: Container ID
        
        Returns:
            True if installation successful
        """
        if self.mock:
            logger.info(f"MOCK: Would install Docker in container {vmid}")
            return True

        logger.info(f"Installing Docker in container {vmid}...")

        # Check if already installed
        if self._check_command_exists(vmid, 'docker'):
            logger.info(f"Docker already installed in container {vmid}")
            return True

        # Install Docker
        install_script = """
        apt-get update
        apt-get install -y ca-certificates curl gnupg
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg
        
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
        
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        systemctl enable docker
        systemctl start docker
        """

        success = self._exec_in_container(vmid, install_script)
        
        if success:
            logger.info(f"✓ Docker installed in container {vmid}")
        else:
            logger.error(f"✗ Docker installation failed in container {vmid}")
        
        return success

    def install_portainer(self, vmid: int) -> bool:
        """Install Portainer web UI for Docker management.
        
        Requires Docker to be installed first.
        
        Args:
            vmid: Container ID
        
        Returns:
            True if installation successful
        """
        if self.mock:
            logger.info(f"MOCK: Would install Portainer in container {vmid}")
            return True

        logger.info(f"Installing Portainer in container {vmid}...")

        # Check if Docker is installed
        if not self._check_command_exists(vmid, 'docker'):
            logger.error(f"Docker not installed in container {vmid}, install docker first")
            return False

        # Install Portainer
        install_script = """
        docker volume create portainer_data
        docker run -d \
          -p 9000:9000 \
          -p 9443:9443 \
          --name portainer \
          --restart=always \
          -v /var/run/docker.sock:/var/run/docker.sock \
          -v portainer_data:/data \
          portainer/portainer-ce:latest
        """

        success = self._exec_in_container(vmid, install_script)
        
        if success:
            logger.info(f"✓ Portainer installed in container {vmid}")
            logger.info(f"  Access Portainer at: http://<container-ip>:9000")
        else:
            logger.error(f"✗ Portainer installation failed in container {vmid}")
        
        return success

    @retry(max_attempts=3, delay=5, exceptions=(subprocess.CalledProcessError,))
    def run_tteck_script(self, vmid: int, script_name: str) -> bool:
        """Run a tteck Proxmox Helper Script inside container with retry on failure.

        Downloads and executes community-maintained installation scripts.

        Args:
            vmid: Container ID
            script_name: Name of tteck script (e.g., 'jellyfin', 'immich')

        Returns:
            True if script completed successfully

        Note:
            Automatically retries up to 3 times with exponential backoff on network failures
        """
        if self.mock:
            logger.info(f"MOCK: Would run tteck/{script_name} in container {vmid}")
            return True

        if script_name not in self.TTECK_SCRIPTS:
            logger.warning(f"Unknown tteck script: {script_name}")
            logger.info(f"Known scripts: {', '.join(self.TTECK_SCRIPTS.keys())}")
            logger.info(f"Attempting to run anyway...")

        # Construct script filename
        script_file = self.TTECK_SCRIPTS.get(script_name, f"{script_name}-install.sh")
        script_url = f"{self.TTECK_BASE_URL}/{script_file}"

        logger.info(f"Running tteck/{script_name} in container {vmid}")
        logger.info(f"  Script: {script_url}")

        # Download and execute script
        install_command = f"""
        apt-get update && apt-get install -y curl bash
        bash -c "$(curl -fsSL {script_url})"
        """

        try:
            success = self._exec_in_container(vmid, install_command)

            if success:
                logger.info(f"✓ tteck/{script_name} completed in container {vmid}")
                return True
            else:
                logger.error(f"✗ tteck/{script_name} failed in container {vmid}")
                raise subprocess.CalledProcessError(1, f"tteck/{script_name}")
        except Exception as e:
            # Re-raise to trigger retry
            raise subprocess.CalledProcessError(1, f"tteck/{script_name}")

    def run_custom_command(self, vmid: int, command: str) -> bool:
        """Run custom shell command(s) inside container.
        
        Args:
            vmid: Container ID
            command: Shell command or multiline script
        
        Returns:
            True if command completed successfully
        """
        if self.mock:
            logger.info(f"MOCK: Would run custom command in container {vmid}")
            logger.debug(f"Command: {command[:100]}...")
            return True

        logger.info(f"Running custom command in container {vmid}")
        logger.debug(f"Command: {command}")

        return self._exec_in_container(vmid, command)

    def _exec_in_container(self, vmid: int, command: str) -> bool:
        """Execute command inside container via pct exec.

        Args:
            vmid: Container ID
            command: Shell command to run

        Returns:
            True if command succeeded
        """
        config = get_config()

        try:
            # Use pct exec to run command in container
            result = subprocess.run(
                ['pct', 'exec', str(vmid), '--', 'bash', '-c', command],
                capture_output=True,
                text=True,
                timeout=config.post_install_timeout
            )
            
            if result.returncode == 0:
                logger.debug(f"Command output: {result.stdout}")
                return True
            else:
                logger.error(f"Command failed with exit code {result.returncode}")
                logger.error(f"stderr: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after 10 minutes")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error running command: {e}")
            return False

    def _check_command_exists(self, vmid: int, command: str) -> bool:
        """Check if a command exists in container.

        Args:
            vmid: Container ID
            command: Command name to check

        Returns:
            True if command exists
        """
        config = get_config()
        check_script = f"command -v {command} >/dev/null 2>&1"

        try:
            result = subprocess.run(
                ['pct', 'exec', str(vmid), '--', 'bash', '-c', check_script],
                capture_output=True,
                timeout=config.command_check_timeout
            )
            return result.returncode == 0
        except:
            return False

    def wait_for_container_boot(self, vmid: int, timeout: int = None) -> bool:
        """Wait for container to finish booting.

        Args:
            vmid: Container ID
            timeout: Maximum seconds to wait (uses config default if None)

        Returns:
            True if container is ready
        """
        if self.mock:
            return True

        config = get_config()
        actual_timeout = timeout if timeout is not None else config.container_boot_timeout

        logger.debug(f"Waiting for container {vmid} to boot...")

        for i in range(actual_timeout):
            try:
                # Try to run simple command
                result = subprocess.run(
                    ['pct', 'exec', str(vmid), '--', 'echo', 'ready'],
                    capture_output=True,
                    timeout=config.container_ready_timeout
                )
                if result.returncode == 0:
                    logger.debug(f"Container {vmid} ready after {i}s")
                    return True
            except:
                pass

            time.sleep(1)

        logger.warning(f"Container {vmid} not ready after {actual_timeout}s")
        return False
