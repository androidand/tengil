"""
Docker container, image, and compose stack discovery.

Discovers running containers, available images, and compose stacks
on local or remote Docker hosts.
"""

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ContainerInfo:
    """Information about a Docker container."""
    id: str
    name: str
    image: str
    status: str
    ports: List[str] = field(default_factory=list)
    volumes: List[Dict[str, str]] = field(default_factory=list)
    networks: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    compose_project: Optional[str] = None
    compose_service: Optional[str] = None


@dataclass
class ImageInfo:
    """Information about a Docker image."""
    id: str
    repository: str
    tag: str
    size: str
    created: str


@dataclass
class ComposeStack:
    """Information about a Docker Compose stack."""
    project: str
    services: List[str] = field(default_factory=list)
    containers: List[str] = field(default_factory=list)


class DockerDiscovery:
    """
    Discover Docker containers, images, and compose stacks.
    
    Supports both local and remote Docker hosts via Docker CLI.
    Uses CLI approach for compatibility and remote access.
    """
    
    def __init__(self, host: Optional[str] = None, context: Optional[str] = None):
        """
        Initialize Docker discovery.
        
        Args:
            host: Docker host URL (tcp://host:2375, ssh://user@host)
                  If None, uses default Docker socket
            context: Docker context name to use
        """
        self.host = host
        self.context = context
        self._check_docker_available()
    
    def _check_docker_available(self) -> bool:
        """Check if Docker is available."""
        try:
            result = self._run_docker(['version', '--format', '{{.Server.Version}}'])
            return result is not None
        except Exception:
            return False
    
    def _run_docker(self, args: List[str], check: bool = True) -> Optional[str]:
        """
        Run docker command with host/context configuration.
        
        Args:
            args: Docker command arguments
            check: Raise exception on failure
            
        Returns:
            Command output or None if failed
        """
        cmd = ['docker']
        
        # Add host or context
        if self.context:
            cmd.extend(['--context', self.context])
        elif self.host:
            cmd.extend(['--host', self.host])
        
        cmd.extend(args)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check,
                timeout=30
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except subprocess.CalledProcessError as e:
            if check:
                raise RuntimeError(f"Docker command failed: {e.stderr}")
            return None
        except subprocess.TimeoutExpired:
            if check:
                raise RuntimeError("Docker command timed out")
            return None
    
    # Container Discovery
    
    def list_containers(self, all: bool = False) -> List[ContainerInfo]:
        """
        List Docker containers.
        
        Args:
            all: Include stopped containers
            
        Returns:
            List of ContainerInfo objects
        """
        args = ['ps', '--format', 'json']
        if all:
            args.append('--all')
        
        output = self._run_docker(args)
        if not output:
            return []
        
        containers = []
        for line in output.split('\n'):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                container = ContainerInfo(
                    id=data.get('ID', ''),
                    name=data.get('Names', ''),
                    image=data.get('Image', ''),
                    status=data.get('State', ''),
                    ports=data.get('Ports', '').split(', ') if data.get('Ports') else []
                )
                containers.append(container)
            except json.JSONDecodeError:
                continue
        
        return containers
    
    def get_container_info(self, container_id: str) -> Optional[ContainerInfo]:
        """
        Get detailed information about a container.
        
        Args:
            container_id: Container ID or name
            
        Returns:
            ContainerInfo with full details or None if not found
        """
        output = self._run_docker(['inspect', container_id], check=False)
        if not output:
            return None
        
        try:
            data = json.loads(output)[0]
            config = data.get('Config', {})
            state = data.get('State', {})
            network_settings = data.get('NetworkSettings', {})
            mounts = data.get('Mounts', [])
            
            # Parse volumes
            volumes = []
            for mount in mounts:
                volumes.append({
                    'source': mount.get('Source', ''),
                    'destination': mount.get('Destination', ''),
                    'mode': mount.get('Mode', ''),
                    'type': mount.get('Type', '')
                })
            
            # Parse environment
            environment = {}
            for env in config.get('Env', []):
                if '=' in env:
                    key, value = env.split('=', 1)
                    # Filter sensitive values
                    if any(secret in key.upper() for secret in ['PASSWORD', 'SECRET', 'TOKEN', 'KEY']):
                        value = '***REDACTED***'
                    environment[key] = value
            
            # Parse labels
            labels = config.get('Labels') or {}
            
            # Detect compose project
            compose_project = labels.get('com.docker.compose.project')
            compose_service = labels.get('com.docker.compose.service')
            
            # Parse networks
            networks = list(network_settings.get('Networks', {}).keys())
            
            # Parse ports
            ports = []
            port_bindings = network_settings.get('Ports', {})
            for container_port, bindings in port_bindings.items():
                if bindings:
                    for binding in bindings:
                        host_ip = binding.get('HostIp', '0.0.0.0')
                        host_port = binding.get('HostPort', '')
                        ports.append(f"{host_ip}:{host_port}->{container_port}")
            
            return ContainerInfo(
                id=data.get('Id', '')[:12],
                name=data.get('Name', '').lstrip('/'),
                image=config.get('Image', ''),
                status=state.get('Status', ''),
                ports=ports,
                volumes=volumes,
                networks=networks,
                environment=environment,
                labels=labels,
                compose_project=compose_project,
                compose_service=compose_service
            )
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            raise RuntimeError(f"Failed to parse container info: {e}")
    
    def search_containers(self, pattern: str) -> List[ContainerInfo]:
        """
        Search containers by name or image.
        
        Args:
            pattern: Search pattern (case-insensitive)
            
        Returns:
            List of matching containers
        """
        containers = self.list_containers(all=True)
        pattern_lower = pattern.lower()
        
        return [
            c for c in containers
            if pattern_lower in c.name.lower() or pattern_lower in c.image.lower()
        ]
    
    # Image Discovery
    
    def list_images(self) -> List[ImageInfo]:
        """
        List local Docker images.
        
        Returns:
            List of ImageInfo objects
        """
        output = self._run_docker(['images', '--format', 'json'])
        if not output:
            return []
        
        images = []
        for line in output.split('\n'):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                image = ImageInfo(
                    id=data.get('ID', ''),
                    repository=data.get('Repository', ''),
                    tag=data.get('Tag', ''),
                    size=data.get('Size', ''),
                    created=data.get('CreatedSince', '')
                )
                images.append(image)
            except json.JSONDecodeError:
                continue
        
        return images
    
    def search_hub(self, term: str, limit: int = 25) -> List[Dict[str, str]]:
        """
        Search Docker Hub for images.
        
        Args:
            term: Search term
            limit: Maximum results (default 25)
            
        Returns:
            List of image metadata dicts
        """
        output = self._run_docker(['search', '--format', 'json', '--limit', str(limit), term])
        if not output:
            return []
        
        results = []
        for line in output.split('\n'):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                results.append({
                    'name': data.get('Name', ''),
                    'description': data.get('Description', ''),
                    'stars': data.get('StarCount', 0),
                    'official': data.get('IsOfficial', False),
                    'automated': data.get('IsAutomated', False)
                })
            except json.JSONDecodeError:
                continue
        
        return results
    
    def get_image_info(self, image: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed image information (exposed ports, volumes, env).
        
        Args:
            image: Image name (e.g., 'nginx:latest')
            
        Returns:
            Dict with image metadata or None if not found
        """
        output = self._run_docker(['inspect', image], check=False)
        if not output:
            return None
        
        try:
            data = json.loads(output)[0]
            config = data.get('Config', {})
            
            return {
                'id': data.get('Id', ''),
                'created': data.get('Created', ''),
                'architecture': data.get('Architecture', ''),
                'os': data.get('Os', ''),
                'size': data.get('Size', 0),
                'exposed_ports': list(config.get('ExposedPorts', {}).keys()),
                'volumes': list(config.get('Volumes', {}).keys()),
                'environment': config.get('Env', []),
                'entrypoint': config.get('Entrypoint', []),
                'cmd': config.get('Cmd', []),
                'labels': config.get('Labels', {})
            }
        except (json.JSONDecodeError, KeyError, IndexError):
            return None
    
    # Compose Stack Discovery
    
    def list_compose_stacks(self) -> List[ComposeStack]:
        """
        List running Docker Compose stacks (by project label).
        
        Returns:
            List of ComposeStack objects
        """
        containers = self.list_containers(all=False)
        stacks: Dict[str, ComposeStack] = {}
        
        for container in containers:
            # Get full info to access labels
            info = self.get_container_info(container.id)
            if not info or not info.compose_project:
                continue
            
            project = info.compose_project
            if project not in stacks:
                stacks[project] = ComposeStack(project=project)
            
            stacks[project].containers.append(info.name)
            if info.compose_service and info.compose_service not in stacks[project].services:
                stacks[project].services.append(info.compose_service)
        
        return list(stacks.values())
    
    def get_stack_services(self, project: str) -> List[ContainerInfo]:
        """
        Get all containers in a Compose stack.
        
        Args:
            project: Compose project name
            
        Returns:
            List of containers in the stack
        """
        containers = self.list_containers(all=False)
        stack_containers = []
        
        for container in containers:
            info = self.get_container_info(container.id)
            if info and info.compose_project == project:
                stack_containers.append(info)
        
        return stack_containers
    
    # Reverse Engineering
    
    def reverse_engineer_compose(self, container_id: str) -> Optional[Dict[str, Any]]:
        """
        Generate Docker Compose configuration from running container.
        
        Args:
            container_id: Container ID or name
            
        Returns:
            Compose dict or None if container not found
        """
        info = self.get_container_info(container_id)
        if not info:
            return None
        
        # Build service configuration
        service_config: Dict[str, Any] = {
            'image': info.image,
            'container_name': info.name
        }
        
        # Add ports
        if info.ports:
            ports = []
            for port_mapping in info.ports:
                # Parse "0.0.0.0:8080->80/tcp" format
                if '->' in port_mapping:
                    host_part, container_part = port_mapping.split('->', 1)
                    # Extract port numbers
                    host_port = host_part.split(':')[-1] if ':' in host_part else host_part
                    container_port = container_part.split('/')[0]
                    ports.append(f"{host_port}:{container_port}")
            if ports:
                service_config['ports'] = ports
        
        # Add volumes
        if info.volumes:
            volumes = []
            for vol in info.volumes:
                if vol['type'] == 'bind':
                    mode = ':ro' if 'ro' in vol.get('mode', '') else ''
                    volumes.append(f"{vol['source']}:{vol['destination']}{mode}")
            if volumes:
                service_config['volumes'] = volumes
        
        # Add environment (filtered)
        if info.environment:
            env = []
            for key, value in info.environment.items():
                # Skip system env vars
                if key in ['PATH', 'HOSTNAME', 'HOME']:
                    continue
                # Keep redacted secrets as empty
                if value == '***REDACTED***':
                    env.append(f"{key}=")
                else:
                    env.append(f"{key}={value}")
            if env:
                service_config['environment'] = env
        
        # Add networks
        if info.networks and info.networks != ['bridge']:
            service_config['networks'] = info.networks
        
        # Add restart policy (assume unless-stopped)
        service_config['restart'] = 'unless-stopped'
        
        # Build compose dict
        compose = {
            'services': {
                info.compose_service or info.name: service_config
            }
        }
        
        # Add networks section if custom networks
        if info.networks and info.networks != ['bridge']:
            compose['networks'] = {net: {'external': True} for net in info.networks}
        
        return compose
