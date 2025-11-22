"""
Docker Compose Deployment - Deploy compose files to LXC containers.

This module handles the final step of the apply workflow:
1. Container exists ✓
2. Datasets mounted ✓
3. Docker installed ✓
4. NOW: Deploy docker-compose.yml → Container running app services

Works with Proxmox LXC containers that have Docker installed.
"""
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class ComposeDeployer:
    """
    Deploys Docker Compose configurations to LXC containers.

    This is the final step after:
    - Container is created
    - ZFS datasets are mounted
    - Docker is installed (via post_install)

    Example workflow:
        deployer = ComposeDeployer(container_id=123)
        deployer.deploy_compose(compose_content, env_vars)
        deployer.start_services()
    """

    def __init__(self, container_id: int, mock: bool = False):
        """
        Initialize deployer for a specific container.

        Args:
            container_id: Proxmox container VMID
            mock: If True, don't execute actual commands
        """
        self.container_id = container_id
        self.mock = mock
        self.logger = logger

        # Standard paths inside container
        self.compose_dir = Path("/opt/tengil/compose")
        self.compose_file = self.compose_dir / "docker-compose.yml"
        self.env_file = self.compose_dir / ".env"

    def deploy_compose(
        self,
        compose_content: Dict[str, Any],
        env_vars: Optional[Dict[str, str]] = None,
        project_name: Optional[str] = None
    ) -> bool:
        """
        Deploy docker-compose.yml to container.

        Args:
            compose_content: Parsed compose dictionary
            env_vars: Environment variables for .env file
            project_name: Docker Compose project name (defaults to 'app')

        Returns:
            True if deployment successful
        """
        if self.mock:
            self.logger.info(
                f"MOCK: Would deploy compose to container {self.container_id}"
            )
            return True

        project_name = project_name or "app"

        try:
            # Create compose directory in container
            self._exec_in_container(f"mkdir -p {self.compose_dir}")

            # Write docker-compose.yml
            compose_yaml = yaml.dump(
                compose_content,
                default_flow_style=False,
                sort_keys=False
            )
            self._write_file_to_container(self.compose_file, compose_yaml)

            # Write .env file if provided
            if env_vars:
                env_content = "\n".join(
                    f"{key}={value}" for key, value in env_vars.items()
                )
                self._write_file_to_container(self.env_file, env_content)

            self.logger.info(
                f"✓ Deployed compose to container {self.container_id}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"✗ Failed to deploy compose to container {self.container_id}: {e}"
            )
            return False

    def start_services(self, project_name: Optional[str] = None) -> bool:
        """
        Start Docker Compose services.

        Args:
            project_name: Docker Compose project name

        Returns:
            True if services started successfully
        """
        if self.mock:
            self.logger.info(
                f"MOCK: Would start compose services in container {self.container_id}"
            )
            return True

        project_name = project_name or "app"

        try:
            # Pull images first
            self.logger.info(
                f"Pulling images for container {self.container_id}..."
            )
            pull_cmd = (
                f"cd {self.compose_dir} && "
                f"docker compose -p {project_name} pull"
            )
            self._exec_in_container(pull_cmd)

            # Start services
            self.logger.info(
                f"Starting services in container {self.container_id}..."
            )
            up_cmd = (
                f"cd {self.compose_dir} && "
                f"docker compose -p {project_name} up -d"
            )
            self._exec_in_container(up_cmd)

            self.logger.info(
                f"✓ Services started in container {self.container_id}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"✗ Failed to start services in container {self.container_id}: {e}"
            )
            return False

    def stop_services(self, project_name: Optional[str] = None) -> bool:
        """
        Stop Docker Compose services.

        Args:
            project_name: Docker Compose project name

        Returns:
            True if services stopped successfully
        """
        if self.mock:
            self.logger.info(
                f"MOCK: Would stop compose services in container {self.container_id}"
            )
            return True

        project_name = project_name or "app"

        try:
            down_cmd = (
                f"cd {self.compose_dir} && "
                f"docker compose -p {project_name} down"
            )
            self._exec_in_container(down_cmd)

            self.logger.info(
                f"✓ Services stopped in container {self.container_id}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"✗ Failed to stop services in container {self.container_id}: {e}"
            )
            return False

    def get_service_status(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status of Docker Compose services.

        Args:
            project_name: Docker Compose project name

        Returns:
            Dictionary with service status info
        """
        if self.mock:
            return {
                'running': True,
                'services': ['mock-service'],
                'containers': 1
            }

        project_name = project_name or "app"

        try:
            ps_cmd = (
                f"cd {self.compose_dir} && "
                f"docker compose -p {project_name} ps --format json"
            )
            output = self._exec_in_container(ps_cmd, capture_output=True)

            # Parse docker compose ps output
            import json
            services = []
            if output.strip():
                for line in output.strip().split('\n'):
                    service_info = json.loads(line)
                    services.append(service_info)

            return {
                'running': len(services) > 0,
                'services': [s.get('Service', 'unknown') for s in services],
                'containers': len(services)
            }

        except Exception as e:
            self.logger.warning(
                f"Could not get service status for container {self.container_id}: {e}"
            )
            return {
                'running': False,
                'services': [],
                'containers': 0,
                'error': str(e)
            }

    def _exec_in_container(
        self,
        command: str,
        capture_output: bool = False
    ) -> Optional[str]:
        """
        Execute command inside Proxmox container.

        Args:
            command: Shell command to execute
            capture_output: If True, return command output

        Returns:
            Command output if capture_output=True, else None
        """
        import subprocess

        pct_cmd = f"pct exec {self.container_id} -- bash -c '{command}'"

        try:
            if capture_output:
                result = subprocess.run(
                    pct_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.stdout
            else:
                subprocess.run(
                    pct_cmd,
                    shell=True,
                    check=True
                )
                return None

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Command failed in container {self.container_id}: {e}"
            )

    def _write_file_to_container(
        self,
        container_path: Path,
        content: str
    ) -> None:
        """
        Write file content to container.

        Uses temporary file + pct push method.

        Args:
            container_path: Path inside container
            content: File content
        """
        import subprocess

        # Write to temporary file on host
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.tmp') as f:
            f.write(content)
            temp_path = f.name

        try:
            # Push file to container using pct push
            pct_push = (
                f"pct push {self.container_id} "
                f"{temp_path} {container_path}"
            )
            subprocess.run(pct_push, shell=True, check=True)

        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)


class ComposeDeploymentOrchestrator:
    """
    High-level orchestration for deploying compose to multiple containers.

    Integrates with the apply workflow to deploy Docker Compose after
    containers are created and configured.
    """

    def __init__(self, mock: bool = False):
        self.mock = mock
        self.logger = logger

    def deploy_to_container(
        self,
        container_id: int,
        compose_content: Dict[str, Any],
        env_vars: Optional[Dict[str, str]] = None,
        project_name: Optional[str] = None
    ) -> bool:
        """
        Deploy and start Docker Compose in a container.

        This is the high-level method called from the apply workflow.

        Args:
            container_id: Proxmox container VMID
            compose_content: Parsed compose dictionary
            env_vars: Environment variables
            project_name: Docker Compose project name

        Returns:
            True if deployment successful
        """
        deployer = ComposeDeployer(container_id, mock=self.mock)

        # Deploy compose files
        if not deployer.deploy_compose(compose_content, env_vars, project_name):
            return False

        # Start services
        if not deployer.start_services(project_name):
            return False

        # Verify services started
        status = deployer.get_service_status(project_name)
        if status['running']:
            self.logger.info(
                f"✓ {status['containers']} service(s) running in container {container_id}"
            )
            return True
        else:
            self.logger.warning(
                f"⚠ Services deployed but not running in container {container_id}"
            )
            return False
