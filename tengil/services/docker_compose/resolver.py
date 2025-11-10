"""
Compose Resolution System - Multi-strategy Docker Compose acquisition.

This module implements the pragmatic resolution chain:
    cache → source → image → dockerfile

Each strategy tries to provide a working docker-compose.yml, with fallback
to the next strategy on failure. Tengil always gets something runnable.
"""
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import requests
from dataclasses import dataclass

from tengil.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ComposeSource:
    """Result from compose resolution."""
    content: Dict[str, Any]  # Parsed compose YAML
    source_type: str         # 'cache', 'url', 'image', 'dockerfile'
    source_path: str         # Where it came from
    metadata: Dict[str, Any] # Additional info


class ComposeResolver:
    """
    Resolves Docker Compose configurations from multiple sources.
    
    Resolution chain (in priority order):
    1. Cache: Local curated files (instant, tested, works offline)
    2. Source: Remote compose URLs (official, may break)
    3. Image: Generate from Docker image metadata
    4. Dockerfile: Parse and generate compose
    
    Example:
        resolver = ComposeResolver()
        compose = resolver.resolve({
            'cache': 'compose_cache/ollama/docker-compose.yml',
            'image': 'ollama/ollama:latest',
            'ports': ['11434:11434'],
            'volumes': ['/root/.ollama:/root/.ollama']
        })
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize resolver.
        
        Args:
            cache_dir: Directory containing curated compose files
        """
        self.cache_dir = cache_dir or Path(__file__).parent.parent.parent / "compose_cache"
        self.logger = logger
    
    def resolve(self, spec: Dict[str, Any]) -> ComposeSource:
        """
        Resolve compose from package specification.
        
        Tries strategies in order:
        1. cache → 2. source → 3. image → 4. dockerfile
        
        Args:
            spec: Package docker_compose section
            
        Returns:
            ComposeSource with compose content and metadata
            
        Raises:
            ValueError: If no valid source found
        """
        strategies = [
            ('cache', self._try_cache),
            ('source', self._try_source),
            ('image', self._try_image),
            ('dockerfile', self._try_dockerfile),
        ]
        
        for strategy_name, strategy_func in strategies:
            if strategy_name not in spec or not spec[strategy_name]:
                continue
            
            self.logger.info(f"[resolver] Trying strategy: {strategy_name}")
            
            try:
                result = strategy_func(spec)
                if result:
                    self.logger.info(
                        f"[resolver] ✓ Success using {strategy_name}: {result.source_path}"
                    )
                    return result
            except Exception as e:
                self.logger.warning(
                    f"[resolver] Strategy {strategy_name} failed: {e}. Trying next..."
                )
                continue
        
        raise ValueError(
            "No valid compose source found. Tried: " + 
            ", ".join(s for s, _ in strategies if s in spec)
        )
    
    def _try_cache(self, spec: Dict[str, Any]) -> Optional[ComposeSource]:
        """
        Strategy 1: Load from local cache.
        
        Benefits:
        - Instant (no network)
        - Tested and verified
        - Works offline
        - Version controlled
        """
        cache_path = spec.get('cache')
        if not cache_path:
            return None
        
        # Resolve relative to project root
        if not Path(cache_path).is_absolute():
            cache_path = self.cache_dir.parent / cache_path
        else:
            cache_path = Path(cache_path)
        
        if not cache_path.exists():
            raise FileNotFoundError(f"Cache file not found: {cache_path}")
        
        self.logger.debug(f"Loading cached compose: {cache_path}")
        
        with open(cache_path) as f:
            content = yaml.safe_load(f)
        
        if not content or 'services' not in content:
            raise ValueError(f"Invalid cached compose: {cache_path}")
        
        return ComposeSource(
            content=content,
            source_type='cache',
            source_path=str(cache_path),
            metadata={
                'cached': True,
                'offline_capable': True,
                'verified': True
            }
        )
    
    def _try_source(self, spec: Dict[str, Any]) -> Optional[ComposeSource]:
        """
        Strategy 2: Download from remote URL.
        
        Benefits:
        - Official configuration
        - Gets updates from upstream
        
        Risks:
        - Can break if upstream changes
        - Requires network
        - May 404
        """
        source_url = spec.get('source')
        if not source_url:
            return None
        
        self.logger.debug(f"Downloading compose from: {source_url}")
        
        try:
            response = requests.get(source_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(f"Failed to download compose: {e}")
        
        content = yaml.safe_load(response.text)
        
        if not content or 'services' not in content:
            raise ValueError(f"Invalid compose from {source_url}")
        
        return ComposeSource(
            content=content,
            source_type='url',
            source_path=source_url,
            metadata={
                'cached': False,
                'upstream': True,
                'verified': False  # Needs validation
            }
        )
    
    def _try_image(self, spec: Dict[str, Any]) -> Optional[ComposeSource]:
        """
        Strategy 3: Generate compose from Docker image + hints.
        
        Benefits:
        - Works with any published image
        - Simple, clean configs
        - No build step
        
        Uses hints from spec:
        - ports: Port mappings
        - volumes: Volume mounts
        - environment: Environment variables
        """
        image_name = spec.get('image')
        if not image_name:
            return None
        
        self.logger.debug(f"Generating compose for image: {image_name}")
        
        # Extract service name from image (e.g., "ollama/ollama:latest" → "ollama")
        service_name = self._service_name_from_image(image_name)
        
        # Build compose from hints
        service_config = {
            'image': image_name,
            'restart': 'unless-stopped'
        }
        
        # Add ports if specified
        if 'ports' in spec and spec['ports']:
            service_config['ports'] = spec['ports']
        
        # Add volumes if specified
        if 'volumes' in spec and spec['volumes']:
            service_config['volumes'] = spec['volumes']
        
        # Add environment if specified
        if 'environment' in spec and spec['environment']:
            service_config['environment'] = spec['environment']
        
        # Add container name
        service_config['container_name'] = service_name
        
        # Add Tengil metadata
        service_config['labels'] = {
            'tengil.managed': 'true',
            'tengil.origin': 'image',
            'tengil.image': image_name
        }
        
        content = {
            'version': '3.8',
            'services': {
                service_name: service_config
            }
        }
        
        return ComposeSource(
            content=content,
            source_type='image',
            source_path=image_name,
            metadata={
                'generated': True,
                'service_name': service_name,
                'base_image': image_name
            }
        )
    
    def _try_dockerfile(self, spec: Dict[str, Any]) -> Optional[ComposeSource]:
        """
        Strategy 4: Parse Dockerfile and generate compose.
        
        Benefits:
        - Maximum flexibility
        - Can customize builds
        
        Drawbacks:
        - Slowest (build time)
        - More complex
        
        Note: This is a placeholder for future implementation.
        """
        dockerfile = spec.get('dockerfile')
        if not dockerfile:
            return None
        
        # TODO: Implement Dockerfile parsing and compose generation
        # For now, raise NotImplementedError
        raise NotImplementedError(
            "Dockerfile parsing not yet implemented. "
            "Use 'image' or 'cache' strategies instead."
        )
    
    def _service_name_from_image(self, image_name: str) -> str:
        """
        Extract service name from Docker image name.
        
        Examples:
            "ollama/ollama:latest" → "ollama"
            "nginx:alpine" → "nginx"
            "registry.example.com/myapp:v1" → "myapp"
        """
        # Remove tag
        base = image_name.split(':')[0]
        
        # Get last component (handle registry.com/org/name)
        parts = base.split('/')
        name = parts[-1]
        
        # If it's org/name format, use the name part
        if len(parts) == 2 and '.' not in parts[0]:
            name = parts[-1]
        
        return name
    
    def save_to_cache(self, compose: ComposeSource, cache_path: str) -> Path:
        """
        Save a working compose to cache for future use.
        
        This enables "learning" - successful composes can be cached
        for faster, reliable reuse.
        
        Args:
            compose: The working compose source
            cache_path: Relative path in cache (e.g., "ollama/docker-compose.yml")
            
        Returns:
            Path to saved cache file
        """
        target = self.cache_dir / cache_path
        target.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target, 'w') as f:
            yaml.dump(compose.content, f, default_flow_style=False, sort_keys=False)
        
        # Save metadata
        metadata_path = target.parent / "metadata.yml"
        metadata = {
            'source_type': compose.source_type,
            'source_path': compose.source_path,
            'cached_at': '2025-11-10',  # TODO: Use actual timestamp
            'verified': compose.metadata.get('verified', False),
            'origin_metadata': compose.metadata
        }
        
        with open(metadata_path, 'w') as f:
            yaml.dump(metadata, f, default_flow_style=False)
        
        self.logger.info(f"[resolver] Saved to cache: {target}")
        
        return target
