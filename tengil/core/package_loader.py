"""Package management for Tengil preset configurations."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
import yaml
from jinja2 import Environment, BaseLoader, TemplateError

from tengil.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PackagePrompt:
    """User input prompt for package customization."""
    id: str
    prompt: str
    default: Any
    type: str = "string"  # string, int, bool
    validate: Optional[str] = None  # regex pattern
    min: Optional[int] = None
    max: Optional[int] = None


@dataclass
class PackageRequirements:
    """System requirements for package."""
    min_ram_mb: Optional[int] = None
    min_disk_gb: Optional[int] = None
    recommended_ram_mb: Optional[int] = None
    recommended_cores: Optional[int] = None


@dataclass
class Package:
    """Tengil package definition."""
    name: str
    slug: str
    description: str
    category: str
    tags: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)
    requirements: Optional[PackageRequirements] = None
    prompts: List[PackagePrompt] = field(default_factory=list)
    config_template: str = ""  # Jinja2 template
    notes: str = ""
    related: List[str] = field(default_factory=list)
    file_path: Optional[Path] = None
    # Docker Compose integration
    docker_compose: Optional[Dict[str, Any]] = None
    storage_hints: Optional[Dict[str, Any]] = None
    share_recommendations: Optional[Dict[str, Any]] = None
    container: Optional[Dict[str, Any]] = None


class PackageLoader:
    """Loads and manages Tengil packages."""

    def __init__(self, package_dir: Optional[Path] = None):
        """Initialize package loader.
        
        Args:
            package_dir: Directory containing package YAML files.
                        Defaults to tengil/packages/
        """
        if package_dir is None:
            # Default to tengil/packages/
            self.package_dir = Path(__file__).parent.parent / "packages"
        else:
            self.package_dir = Path(package_dir)
        
        self.jinja_env = Environment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def list_packages(self, category: Optional[str] = None) -> List[Package]:
        """List available packages.
        
        Args:
            category: Filter by category (e.g., 'media', 'storage')
        
        Returns:
            List of Package objects
        """
        packages = []
        
        if not self.package_dir.exists():
            logger.warning(f"Package directory not found: {self.package_dir}")
            return packages
        
        for yaml_file in self.package_dir.glob("*.yml"):
            if yaml_file.stem in ["README", "__init__", "APP_GUIDE"]:
                continue
            
            try:
                pkg = self.load_package(yaml_file.stem)
                if category is None or pkg.category.lower() == category.lower():
                    packages.append(pkg)
            except Exception as e:
                logger.warning(f"Failed to load package {yaml_file.stem}: {e}")
        
        return sorted(packages, key=lambda p: (p.category, p.name))
    
    def load_package(self, package_name: str) -> Package:
        """Load a specific package by name.
        
        Args:
            package_name: Package slug (e.g., 'media-server', 'nas-basic')
        
        Returns:
            Package object
        
        Raises:
            FileNotFoundError: Package file not found
            ValueError: Invalid package format
        """
        package_file = self.package_dir / f"{package_name}.yml"
        
        if not package_file.exists():
            raise FileNotFoundError(f"Package not found: {package_name}")
        
        return self._load_package_file(package_file, package_name)
    
    def load_package_file(self, package_path: Path | str) -> Package:
        """Load a package from an absolute file path.
        
        Args:
            package_path: Absolute path to package YAML file
            
        Returns:
            Package object
            
        Raises:
            FileNotFoundError: File not found
            ValueError: Invalid package format
        """
        package_file = Path(package_path)
        if not package_file.exists():
            raise FileNotFoundError(f"Package file not found: {package_path}")
        
        # Extract slug from filename
        slug = package_file.stem
        return self._load_package_file(package_file, slug)
    
    def _load_package_file(self, package_file: Path, slug: str) -> Package:
        """Internal method to load a package file.
        
        Args:
            package_file: Path to package file
            slug: Package slug name
            
        Returns:
            Package object
        """
        
        # Read as raw text first (for Jinja2)
        with open(package_file, 'r') as f:
            raw_content = f.read()
        
        # Split into metadata and config sections
        # The config section contains Jinja2 templates
        # Match config: at start of line (not in strings like "/config:/config")
        import re
        config_match = re.search(r'^config:', raw_content, re.MULTILINE)
        if config_match:
            # Parse just the metadata part (before config)
            split_pos = config_match.start()
            metadata_yaml = raw_content[:split_pos]
            # Skip the "config:" line itself, get everything after it
            config_start = config_match.end() + 1  # +1 to skip the newline
            config_section = raw_content[config_start:]
            
            # Parse metadata normally
            data = yaml.safe_load(metadata_yaml)
            
            # Store config section as template (will be rendered later)
            # Dedent the template since it was indented under config:
            import textwrap
            config_template = textwrap.dedent(config_section)
        else:
            # No config section with templates
            data = yaml.safe_load(raw_content)
            config_template = yaml.dump(data.get('config', {}))
        
        if not data:
            raise ValueError(f"Empty package file: {slug}")
        
        # Parse requirements
        requirements = None
        if 'requirements' in data:
            req_data = data['requirements']
            requirements = PackageRequirements(
                min_ram_mb=req_data.get('min_ram_mb'),
                min_disk_gb=req_data.get('min_disk_gb'),
                recommended_ram_mb=req_data.get('recommended_ram_mb'),
                recommended_cores=req_data.get('recommended_cores')
            )
        
        # Parse prompts
        prompts = []
        if 'customize' in data:
            for prompt_data in data['customize']:
                prompts.append(PackagePrompt(
                    id=prompt_data['key'],
                    prompt=prompt_data['prompt'],
                    default=prompt_data['default'],
                    type=prompt_data.get('type', 'string'),
                    validate=prompt_data.get('validate'),
                    min=prompt_data.get('min'),
                    max=prompt_data.get('max')
                ))
        
        return Package(
            name=data.get('name', slug),
            slug=slug,
            description=data.get('description', ''),
            category=data.get('category', 'other'),
            tags=data.get('tags', []),
            components=data.get('components', []),
            requirements=requirements,
            prompts=prompts,
            config_template=config_template,
            notes=data.get('notes', ''),
            related=data.get('related', []),
            file_path=package_file,
            # Docker Compose integration fields
            docker_compose=data.get('docker_compose'),
            storage_hints=data.get('storage_hints'),
            share_recommendations=data.get('share_recommendations'),
            container=data.get('container')
        )
    
    def search_packages(self, query: str) -> List[Package]:
        """Search packages by name, description, or tags.
        
        Args:
            query: Search query
        
        Returns:
            List of matching Package objects
        """
        query = query.lower()
        packages = self.list_packages()
        
        matches = []
        for pkg in packages:
            if (query in pkg.name.lower() or
                query in pkg.description.lower() or
                any(query in tag.lower() for tag in pkg.tags)):
                matches.append(pkg)
        
        return matches
    
    def render_config(self, package: Package, user_inputs: Dict[str, Any]) -> Dict:
        """Render package config with user inputs.

        Args:
            package: Package to render
            user_inputs: Dictionary of user input values (prompt id -> value)

        Returns:
            Rendered configuration dictionary

        Raises:
            TemplateError: If rendering fails
        """
        try:
            # Merge user inputs with defaults from prompts
            render_context = {}
            for prompt in package.prompts:
                # Use user input if provided, otherwise use default
                render_context[prompt.id] = user_inputs.get(prompt.id, prompt.default)

            # Render the config template with Jinja2
            template = self.jinja_env.from_string(package.config_template)
            rendered_yaml = template.render(**render_context)

            # Parse rendered YAML back to dict
            config = yaml.safe_load(rendered_yaml) or {}

            # Normalize structure: some templates omit explicit indentation
            # causing pool definitions to be emitted at the top level with
            # `pools: null`. In that case, move those pool entries under the
            # pools mapping so downstream code receives the expected shape.
            if isinstance(config, dict):
                # Ensure version metadata exists for downstream tooling.
                config.setdefault('version', 2)
                pools_value = config.get('pools')
                if pools_value is None:
                    pool_entries: Dict[str, Any] = {}
                    for key in list(config.keys()):
                        if key == 'pools':  # keep sentinel for later replacement
                            continue
                        value = config[key]
                        if isinstance(value, dict) and ('datasets' in value or 'type' in value):
                            pool_entries[key] = config.pop(key)
                    if pool_entries:
                        config['pools'] = pool_entries

            return config

        except TemplateError as e:
            logger.error(f"Failed to render package template: {e}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML after rendering: {e}")
            raise
    
    def render_compose_config(self, package: Package, user_inputs: Dict[str, Any]) -> Dict:
        """Generate config from Docker Compose package using resolver + analyzer + merger.
        
        Args:
            package: Package with docker_compose section
            user_inputs: Dictionary of user input values
            
        Returns:
            Generated tengil.yml configuration
            
        Raises:
            ValueError: If docker_compose section missing or invalid
        """
        if not package.docker_compose:
            raise ValueError(f"Package {package.slug} does not have docker_compose section")
        
        # Import here to avoid circular dependency
        from tengil.services.docker_compose import ComposeAnalyzer, OpinionMerger, ComposeResolver
        
        # Resolve compose using multi-strategy resolver
        logger.info(f"Resolving Docker Compose for package: {package.slug}")
        
        # Get cache directory (compose_cache/ relative to tengil root)
        cache_dir = Path(__file__).parent.parent.parent / "compose_cache"
        resolver = ComposeResolver(cache_dir=cache_dir)
        
        # Extract first source from sources array (if present)
        compose_spec = package.docker_compose
        if 'sources' in compose_spec and isinstance(compose_spec['sources'], list):
            # New format: docker_compose.sources[0]
            compose_spec = compose_spec['sources'][0]
        
        # Resolve compose spec (cache → source → image → dockerfile)
        compose_result = resolver.resolve(compose_spec)
        
        logger.info(f"✓ Resolved compose using strategy: {compose_result.source_type}")
        logger.info(f"  Source: {compose_result.source_path}")
        logger.info(f"  Services: {list(compose_result.content.get('services', {}).keys())}")
        
        # Save to cache if it was generated (for future use)
        if compose_result.source_type in ['image', 'dockerfile'] and not compose_result.metadata.get('cached'):
            # Generate cache path from package slug
            cache_path = cache_dir / package.slug / "docker-compose.yml"
            logger.info(f"Saving generated compose to cache: {cache_path}")
            resolver.save_to_cache(compose_result.content, cache_path)
        
        # Analyze compose requirements
        analyzer = ComposeAnalyzer()
        requirements = analyzer.analyze_dict(compose_result.content)
        
        logger.info(f"Found {len(requirements.volumes)} volumes, {len(requirements.secrets)} secrets")
        
        # Build package data for merger
        package_data = {
            'storage_hints': package.storage_hints or {},
            'share_recommendations': package.share_recommendations or {},
            'container': package.container or {}
        }
        
        # Merge with Tengil opinions
        merger = OpinionMerger()
        config = merger.merge(requirements, package_data)
        
        # Apply user inputs to pool name
        if 'pool_name' in user_inputs:
            pool_name = user_inputs['pool_name']
            # Rename pool from 'tank' to user's choice
            if 'tank' in config['pools']:
                config['pools'][pool_name] = config['pools'].pop('tank')
        
        return config
    
    def get_categories(self) -> Dict[str, List[Package]]:
        """Get packages grouped by category.
        
        Returns:
            Dictionary of category -> List[Package]
        """
        packages = self.list_packages()
        categories = {}
        
        for pkg in packages:
            category = pkg.category
            if category not in categories:
                categories[category] = []
            categories[category].append(pkg)
        
        return categories
