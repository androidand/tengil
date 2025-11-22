"""
Docker Compose to Tengil Config Converter.

Converts Docker Compose files into Tengil YAML configurations automatically.
Maps compose volumes to ZFS datasets, extracts resources, and generates
ready-to-deploy container specs.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from tengil.services.docker_compose.analyzer import ComposeAnalyzer, ComposeRequirements


@dataclass
class DatasetSpec:
    """Specification for a ZFS dataset."""
    name: str  # Dataset name (e.g., "immich-photos")
    profile: str  # ZFS profile: media, appdata, database, downloads
    mount_point: str  # Mount point in container (e.g., "/photos")
    readonly: bool = False
    size_estimate: str = "50G"  # Conservative default
    justification: str = ""  # Why this profile was chosen


@dataclass
class ConversionResult:
    """Result of converting a compose file to Tengil config."""
    app_name: str
    pool: str
    datasets: List[DatasetSpec]
    container_name: str
    container_memory: int  # MB
    container_cores: int
    docker_compose_path: str  # Path/URL to compose file
    secrets_needed: List[str]
    ports: List[str]
    services: List[str]
    warnings: List[str] = field(default_factory=list)


class ComposeConverter:
    """
    Converts Docker Compose files into Tengil YAML configurations.

    Analyzes compose files and generates:
    - ZFS dataset specifications with optimal profiles
    - Container resource allocations
    - Mount configurations
    - Secret detection
    """

    # Path patterns for dataset profile classification
    PATH_PATTERNS = {
        "media": [
            r"/(photos?|pictures?|images?)",
            r"/(videos?|movies?|tv|shows?)",
            r"/(music|audio)",
            r"/media",
        ],
        "database": [
            r"/(db|database)",
            r"/postgres(ql)?",
            r"/mysql",
            r"/mariadb",
            r"/mongodb",
            r"/redis",
            r"/var/lib/(postgres|mysql|mongodb)",
        ],
        "downloads": [
            r"/(downloads?|torrents?)",
            r"/incoming",
            r"/queue",
        ],
        "appdata": [
            r"/(config|configs?|settings?)",
            r"/(data|app|appdata)",
            r"/(cache|tmp|temp)",
            r"/var/lib/.*",
        ],
    }

    # Size heuristics: (profile, path_hint) -> size
    SIZE_HEURISTICS = {
        ("media", "photo"): "2T",
        ("media", "video"): "5T",
        ("media", "movie"): "5T",
        ("media", "music"): "500G",
        ("media", "media"): "2T",  # Generic media
        ("database", "postgres"): "100G",
        ("database", "mysql"): "100G",
        ("database", "redis"): "50G",
        ("database", "db"): "100G",  # Generic database
        ("downloads", "download"): "500G",
        ("downloads", "torrent"): "500G",
        ("appdata", "config"): "10G",
        ("appdata", "data"): "50G",
        ("appdata", "cache"): "20G",
    }

    # Default resource allocations by profile
    DEFAULT_RESOURCES = {
        "media": {"memory": 4096, "cores": 2},  # Media servers need RAM
        "database": {"memory": 2048, "cores": 2},  # Databases need CPU
        "web": {"memory": 2048, "cores": 2},  # Generic web apps
        "unknown": {"memory": 2048, "cores": 2},  # Conservative default
    }

    def __init__(self):
        self.analyzer = ComposeAnalyzer()

    def convert(
        self,
        compose_path: str,
        pool: str = "tank",
        app_name: Optional[str] = None,
    ) -> ConversionResult:
        """
        Convert a Docker Compose file into Tengil configuration.

        Args:
            compose_path: Path or URL to docker-compose.yml
            pool: ZFS pool to use (default: tank)
            app_name: Application name (auto-detected from compose if not provided)

        Returns:
            ConversionResult with all configuration specs
        """
        # Analyze compose file
        requirements = self.analyzer.analyze(compose_path)

        # Determine app name
        if not app_name:
            app_name = self._detect_app_name(compose_path, requirements)

        # Generate dataset specifications
        datasets = self._plan_datasets(requirements, app_name)

        # Determine resource allocation
        app_type = self._classify_app(requirements)
        resources = self.DEFAULT_RESOURCES.get(app_type, self.DEFAULT_RESOURCES["unknown"])

        # Build result
        result = ConversionResult(
            app_name=app_name,
            pool=pool,
            datasets=datasets,
            container_name=app_name,
            container_memory=resources["memory"],
            container_cores=resources["cores"],
            docker_compose_path=compose_path,
            secrets_needed=sorted(list(requirements.secrets)),
            ports=requirements.ports,
            services=requirements.services,
        )

        # Add warnings
        if len(requirements.services) > 1:
            result.warnings.append(
                f"Multi-service compose ({len(requirements.services)} services). "
                "All services will run in one LXC container via Docker Compose."
            )

        if not datasets:
            result.warnings.append(
                "No host volume mounts detected. App may use named volumes "
                "(not managed by Tengil) or store data inside container."
            )

        return result

    def _detect_app_name(self, compose_path: str, requirements: ComposeRequirements) -> str:
        """Detect application name from compose file or service names."""
        # Try to extract from file path
        path = Path(compose_path)
        parent_dir = path.parent.name

        # If parent dir is a real app name (not generic), use it
        if parent_dir not in ("", ".", "compose", "docker", "configs"):
            return self._sanitize_name(parent_dir)

        # Otherwise use first service name
        if requirements.services:
            return self._sanitize_name(requirements.services[0])

        return "app"

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for use as dataset/container name."""
        # Convert to lowercase, replace invalid chars with dash
        name = re.sub(r'[^a-z0-9-]', '-', name.lower())
        # Remove leading/trailing dashes
        name = name.strip('-')
        # Collapse multiple dashes
        name = re.sub(r'-+', '-', name)
        return name or "app"

    def _plan_datasets(
        self,
        requirements: ComposeRequirements,
        app_name: str
    ) -> List[DatasetSpec]:
        """Plan ZFS datasets from volume requirements."""
        datasets = []

        for volume in requirements.volumes:
            # Classify the path to determine profile
            profile, justification = self._classify_path(volume.container)

            # Generate dataset name
            purpose = self._extract_purpose(volume.container)
            dataset_name = f"{app_name}-{purpose}"

            # Estimate size
            size = self._estimate_size(profile, volume.container)

            datasets.append(DatasetSpec(
                name=dataset_name,
                profile=profile,
                mount_point=volume.container,
                readonly=volume.readonly,
                size_estimate=size,
                justification=justification,
            ))

        return datasets

    def _classify_path(self, path: str) -> tuple[str, str]:
        """
        Classify a container path to determine optimal ZFS profile.

        Returns:
            (profile_name, justification)
        """
        path_lower = path.lower()

        for profile, patterns in self.PATH_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, path_lower):
                    return profile, f"Path '{path}' matches {profile} pattern"

        # Default to appdata
        return "appdata", f"No specific pattern match for '{path}', using appdata profile"

    def _extract_purpose(self, path: str) -> str:
        """Extract purpose from path for dataset naming."""
        # Strip leading/trailing slashes
        path = path.strip('/')

        # Get last component
        parts = path.split('/')
        purpose = parts[-1] if parts else "data"

        # Sanitize
        purpose = re.sub(r'[^a-z0-9-]', '-', purpose.lower())
        purpose = purpose.strip('-')
        purpose = re.sub(r'-+', '-', purpose)

        return purpose or "data"

    def _estimate_size(self, profile: str, path: str) -> str:
        """Estimate dataset size based on profile and path."""
        path_lower = path.lower()

        # Try specific heuristics first
        for (heuristic_profile, hint), size in self.SIZE_HEURISTICS.items():
            if profile == heuristic_profile and hint in path_lower:
                return size

        # Fall back to profile defaults
        defaults = {
            "media": "1T",  # Large by default
            "database": "100G",
            "downloads": "500G",
            "appdata": "50G",
        }

        return defaults.get(profile, "50G")

    def _classify_app(self, requirements: ComposeRequirements) -> str:
        """Classify app type based on services and requirements."""
        service_names = " ".join(requirements.services).lower()

        # Check for media keywords
        media_keywords = ["jellyfin", "plex", "emby", "immich", "photoprism", "media", "photo"]
        if any(keyword in service_names for keyword in media_keywords):
            return "media"

        # Check for database keywords
        db_keywords = ["postgres", "mysql", "mariadb", "mongodb", "redis", "database"]
        if any(keyword in service_names for keyword in db_keywords):
            return "database"

        return "web"

    def to_yaml(self, result: ConversionResult) -> str:
        """
        Convert ConversionResult to Tengil YAML config.

        Returns:
            YAML string ready to be written to tengil.yml
        """
        lines = []

        # Header comment
        lines.append("# Tengil configuration")
        lines.append(f"# Generated from: {result.docker_compose_path}")
        lines.append(f"# App: {result.app_name}")
        if result.warnings:
            lines.append("#")
            lines.append("# Warnings:")
            for warning in result.warnings:
                lines.append(f"#   - {warning}")
        lines.append("")

        # Pools and datasets
        lines.append("pools:")
        lines.append(f"  {result.pool}:")
        lines.append("    datasets:")

        for dataset in result.datasets:
            lines.append(f"      {dataset.name}:")
            lines.append(f"        profile: {dataset.profile}  # {dataset.justification}")
            lines.append(f"        # Estimated size: {dataset.size_estimate}")
            lines.append("        containers:")
            lines.append(f"          - name: {result.container_name}")
            lines.append(f"            mount: {dataset.mount_point}")
            if dataset.readonly:
                lines.append("            readonly: true")
            lines.append("")

        # Container configuration
        lines.append("containers:")
        lines.append(f"  {result.container_name}:")
        lines.append("    auto_create: true")
        lines.append("    template: debian-12-standard")
        lines.append("    privileged: true  # Required for Docker")
        lines.append("    resources:")
        lines.append(f"      memory: {result.container_memory}")
        lines.append(f"      cores: {result.container_cores}")
        lines.append("      disk: 32G")
        lines.append("    requires_docker: true  # Auto-install Docker Engine")
        lines.append("    docker_compose:")
        lines.append(f"      source: {result.docker_compose_path}")

        if result.secrets_needed:
            lines.append("      environment:")
            for secret in result.secrets_needed:
                lines.append(f"        {secret}:  # TODO: Set this value")

        if result.ports:
            lines.append("#    network:")
            lines.append("#      ip: dhcp  # Or static IP like 192.168.1.100/24")
            lines.append(f"#      # Exposed ports: {', '.join(result.ports)}")

        lines.append("")

        return "\n".join(lines)
