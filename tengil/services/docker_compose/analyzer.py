"""
Docker Compose file analyzer.

Parses Docker Compose files to extract infrastructure requirements:
- Host volume mounts
- Required secrets (empty environment variables)
- Exposed ports
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.request import urlopen

import yaml


@dataclass
class VolumeMount:
    """Represents a volume mount from compose file."""
    host: str  # Host path (e.g., "/roms")
    container: str  # Container path (e.g., "/romm/library")
    service: str  # Service name (e.g., "romm")
    readonly: bool = False
    
    def __hash__(self):
        return hash((self.host, self.container, self.service))


@dataclass
class ComposeRequirements:
    """Extracted infrastructure requirements from compose file."""
    volumes: List[VolumeMount] = field(default_factory=list)
    secrets: Set[str] = field(default_factory=set)
    ports: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    
    def add_volume(self, host: str, container: str, service: str, readonly: bool = False):
        """Add a volume mount requirement."""
        mount = VolumeMount(host=host, container=container, service=service, readonly=readonly)
        if mount not in self.volumes:
            self.volumes.append(mount)
    
    def add_secret(self, key: str):
        """Add a secret requirement."""
        self.secrets.add(key)
    
    def add_port(self, port: str):
        """Add a port mapping."""
        if port not in self.ports:
            self.ports.append(port)
    
    def get_host_paths(self) -> Set[str]:
        """Get unique host paths that need datasets."""
        return {vol.host for vol in self.volumes}


class ComposeAnalyzer:
    """
    Analyzes Docker Compose files to extract infrastructure requirements.
    
    Supports:
    - Local file paths
    - Remote URLs (GitHub, GitLab, etc.)
    - Docker Compose v2 and v3 formats
    """
    
    def __init__(self):
        self.logger = None  # TODO: Add logging
    
    def analyze(self, source: str) -> ComposeRequirements:
        """
        Analyze a compose file and extract requirements.
        
        Args:
            source: File path or URL to compose file
            
        Returns:
            ComposeRequirements with extracted infrastructure needs
        """
        compose_content = self._load_compose(source)
        compose = yaml.safe_load(compose_content)
        
        if not compose or 'services' not in compose:
            raise ValueError("Invalid compose file: no services section found")
        
        requirements = ComposeRequirements()
        
        # Process each service
        for service_name, service_config in compose['services'].items():
            requirements.services.append(service_name)
            self._extract_from_service(service_name, service_config, requirements)
        
        return requirements
    
    def analyze_dict(self, compose: dict) -> ComposeRequirements:
        """
        Analyze a compose dictionary (already parsed YAML) and extract requirements.
        
        Args:
            compose: Parsed compose dictionary
            
        Returns:
            ComposeRequirements with extracted infrastructure needs
        """
        if not compose or 'services' not in compose:
            raise ValueError("Invalid compose file: no services section found")
        
        requirements = ComposeRequirements()
        
        # Process each service
        for service_name, service_config in compose['services'].items():
            requirements.services.append(service_name)
            self._extract_from_service(service_name, service_config, requirements)
        
        return requirements
    
    def _load_compose(self, source: str) -> str:
        """Load compose content from file or URL."""
        if source.startswith(('http://', 'https://')):
            return self._download(source)
        else:
            return self._read_file(source)
    
    def _download(self, url: str) -> str:
        """Download compose file from URL."""
        try:
            with urlopen(url, timeout=10) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to download compose from {url}: {e}")
    
    def _read_file(self, path: str) -> str:
        """Read compose file from local path."""
        try:
            return Path(path).read_text()
        except Exception as e:
            raise ValueError(f"Failed to read compose file {path}: {e}")
    
    def _extract_from_service(self, service_name: str, service: dict, 
                              requirements: ComposeRequirements):
        """Extract requirements from a single service."""
        # Extract volumes
        for volume in service.get('volumes', []):
            self._parse_volume(volume, service_name, requirements)
        
        # Extract secrets (empty env vars)
        self._parse_environment(service.get('environment', []), requirements)
        
        # Extract ports
        for port in service.get('ports', []):
            requirements.add_port(str(port))
    
    def _parse_volume(self, volume: str | dict, service_name: str, 
                      requirements: ComposeRequirements):
        """Parse a volume declaration."""
        if isinstance(volume, dict):
            # Long format: {type: bind, source: /host, target: /container}
            if volume.get('type') == 'bind':
                host = volume.get('source', '')
                container = volume.get('target', '')
                readonly = volume.get('read_only', False)
                if host.startswith('/'):
                    requirements.add_volume(host, container, service_name, readonly)
        
        elif isinstance(volume, str):
            # Short format: "/host:/container" or "/host:/container:ro"
            if ':' not in volume:
                return  # Named volume, not host mount
            
            parts = volume.split(':')
            if len(parts) < 2:
                return
            
            host = parts[0]
            container = parts[1]
            readonly = len(parts) > 2 and 'ro' in parts[2]
            
            # Only interested in host mounts (start with /)
            if host.startswith('/'):
                requirements.add_volume(host, container, service_name, readonly)
    
    def _parse_environment(self, environment: list | dict, requirements: ComposeRequirements):
        """Parse environment variables to find secrets (empty values)."""
        if isinstance(environment, dict):
            # Dict format: {KEY: value}
            for key, value in environment.items():
                if value == '' or value is None:
                    requirements.add_secret(key)
        
        elif isinstance(environment, list):
            # List format: ["KEY=value", "KEY2="]
            for env in environment:
                if isinstance(env, str) and '=' in env:
                    key, value = env.split('=', 1)
                    if not value:  # Empty = needs filling
                        requirements.add_secret(key)
    
    def analyze_to_dict(self, source: str) -> dict:
        """
        Analyze compose and return as dictionary (for CLI/debugging).
        
        Returns:
            {
                'volumes': [{'host': '/roms', 'container': '/romm/library', ...}],
                'secrets': ['DB_PASSWD', ...],
                'ports': ['8080:8080', ...],
                'services': ['romm', 'romm-db', ...]
            }
        """
        requirements = self.analyze(source)
        
        return {
            'volumes': [
                {
                    'host': vol.host,
                    'container': vol.container,
                    'service': vol.service,
                    'readonly': vol.readonly
                }
                for vol in requirements.volumes
            ],
            'secrets': sorted(list(requirements.secrets)),
            'ports': requirements.ports,
            'services': requirements.services,
            'host_paths': sorted(list(requirements.get_host_paths()))
        }
