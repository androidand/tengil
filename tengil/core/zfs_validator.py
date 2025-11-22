"""ZFS-specific validation and recommendations.

Validates ZFS configurations and provides recommendations for:
- Record size optimization
- Compression algorithms
- Dataset profiles
- Performance tuning
"""

from enum import Enum
from typing import Dict, List, Optional

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class Severity(Enum):
    """Severity level for validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue:
    """A validation issue with context."""

    def __init__(self, severity: Severity, message: str,
                 dataset: Optional[str] = None,
                 recommendation: Optional[str] = None):
        self.severity = severity
        self.message = message
        self.dataset = dataset
        self.recommendation = recommendation

    def __str__(self):
        prefix = {
            Severity.ERROR: "❌",
            Severity.WARNING: "⚠️",
            Severity.INFO: "💡"
        }[self.severity]

        parts = [f"{prefix} {self.message}"]
        if self.dataset:
            parts.append(f"   Dataset: {self.dataset}")
        if self.recommendation:
            parts.append(f"   💡 Recommendation: {self.recommendation}")

        return "\n".join(parts)


class ZFSValidator:
    """Validates ZFS configurations and provides recommendations."""

    # Optimal recordsize by use case
    RECORDSIZE_RECOMMENDATIONS = {
        'media': {
            'optimal': '1M',
            'reason': 'Large video files (2-50GB) benefit from 1MB blocks',
            'performance_gain': '30% faster sequential reads vs 128K'
        },
        'photos': {
            'optimal': '1M',
            'reason': 'Photos/RAW files are large (5-50MB), sequential access',
            'performance_gain': '25-30% faster reads for large files'
        },
        'downloads': {
            'optimal': '128K',
            'reason': 'Torrent pieces are small (256K-4MB), many random writes',
            'performance_gain': 'Reduces fragmentation, better for many small files'
        },
        'dev': {
            'optimal': '128K',
            'reason': 'Mixed file sizes, databases with 8K-16K blocks',
            'performance_gain': 'Good balance for varied workloads'
        },
        'backups': {
            'optimal': '128K',
            'reason': 'Compressed archives vary in size',
            'performance_gain': 'Compression works better with smaller blocks'
        },
        'database': {
            'optimal': '8K',
            'reason': 'Databases use 8K blocks (PostgreSQL, MySQL)',
            'performance_gain': 'Matches database block size, reduces write amplification'
        },
        'vm': {
            'optimal': '64K',
            'reason': 'VM disk images use 4K-64K I/O',
            'performance_gain': 'Optimal for virtualization workloads'
        }
    }

    # Compression recommendations
    COMPRESSION_RECOMMENDATIONS = {
        'media': {
            'optimal': 'lz4',
            'reason': 'Video already compressed, lz4 is fast with minimal CPU',
            'alternatives': ['off'],  # Media is often incompressible
            'cpu_impact': 'Very low'
        },
        'photos': {
            'optimal': 'lz4',
            'reason': 'JPEG compressed, RAW might compress 10-20%',
            'alternatives': ['zstd-3'],  # Better compression for RAW
            'cpu_impact': 'Low'
        },
        'downloads': {
            'optimal': 'lz4',
            'reason': 'Mixed content, need fast writes for torrents',
            'alternatives': ['off'],  # Speed over compression
            'cpu_impact': 'Low'
        },
        'backups': {
            'optimal': 'gzip-9',
            'reason': 'Backups read rarely, maximize space savings',
            'alternatives': ['zstd-9', 'zstd-19'],
            'cpu_impact': 'High (but acceptable for backups)',
            'space_savings': '3-4x compression ratio typical'
        },
        'documents': {
            'optimal': 'zstd-3',
            'reason': 'Text/docs compress well, zstd fast with good ratio',
            'alternatives': ['lz4', 'zstd-1'],
            'cpu_impact': 'Low',
            'space_savings': '2-3x compression ratio'
        },
        'dev': {
            'optimal': 'lz4',
            'reason': 'Source code compresses well, need fast access',
            'alternatives': ['zstd-1'],
            'cpu_impact': 'Very low'
        }
    }

    # ARC (cache) recommendations
    ARC_RECOMMENDATIONS = {
        'media': {
            'primarycache': 'metadata',
            'secondarycache': 'metadata',
            'reason': 'Large files streamed once, cache metadata only to save RAM'
        },
        'database': {
            'primarycache': 'all',
            'secondarycache': 'all',
            'reason': 'Hot data needs caching, DB queries benefit from ARC'
        },
        'vm': {
            'primarycache': 'all',
            'secondarycache': 'all',
            'reason': 'VM I/O is random, caching improves performance significantly'
        }
    }

    def __init__(self):
        self.issues: List[ValidationIssue] = []

    def validate_dataset(self, dataset_name: str, config: Dict,
                        profile: Optional[str] = None) -> List[ValidationIssue]:
        """Validate a dataset configuration.

        Args:
            dataset_name: Name of the dataset
            config: Dataset configuration
            profile: Optional profile type (media, dev, etc.)

        Returns:
            List of validation issues
        """
        issues = []

        # Get properties
        properties = config.get('properties', {})

        # Validate recordsize
        if 'recordsize' in properties:
            recordsize_issues = self._validate_recordsize(
                dataset_name, properties['recordsize'], profile
            )
            issues.extend(recordsize_issues)
        elif profile:
            # Recommend recordsize if not set
            issues.append(self._recommend_recordsize(dataset_name, profile))

        # Validate compression
        if 'compression' in properties:
            comp_issues = self._validate_compression(
                dataset_name, properties['compression'], profile
            )
            issues.extend(comp_issues)
        elif profile:
            # Recommend compression
            issues.append(self._recommend_compression(dataset_name, profile))

        # Validate atime setting
        if 'atime' not in properties:
            issues.append(ValidationIssue(
                Severity.INFO,
                f"Consider disabling atime for {dataset_name}",
                dataset=dataset_name,
                recommendation="Set 'atime: off' - saves write operations on read access"
            ))

        # Check for sync setting
        if 'sync' in properties and properties['sync'] == 'disabled':
            issues.append(ValidationIssue(
                Severity.WARNING,
                f"sync=disabled on {dataset_name} risks data loss",
                dataset=dataset_name,
                recommendation="Use sync=standard unless you have battery-backed cache"
            ))

        return issues

    def _validate_recordsize(self, dataset: str, recordsize: str,
                           profile: Optional[str]) -> List[ValidationIssue]:
        """Validate recordsize setting."""
        issues = []

        # Parse recordsize (can be like '1M', '128K', etc.)
        try:
            size_bytes = self._parse_size(recordsize)
        except ValueError:
            issues.append(ValidationIssue(
                Severity.ERROR,
                f"Invalid recordsize '{recordsize}' for {dataset}",
                dataset=dataset,
                recommendation="Use values like 4K, 8K, 16K, 32K, 64K, 128K, 256K, 512K, 1M"
            ))
            return issues

        # Check if it's a power of 2
        if size_bytes & (size_bytes - 1) != 0:
            issues.append(ValidationIssue(
                Severity.ERROR,
                f"Recordsize {recordsize} is not a power of 2",
                dataset=dataset,
                recommendation="ZFS requires recordsize to be a power of 2"
            ))

        # Check against profile recommendation
        if profile and profile in self.RECORDSIZE_RECOMMENDATIONS:
            rec = self.RECORDSIZE_RECOMMENDATIONS[profile]
            optimal = rec['optimal']

            if recordsize != optimal:
                issues.append(ValidationIssue(
                    Severity.INFO,
                    f"Recordsize {recordsize} differs from optimal {optimal} for {profile}",
                    dataset=dataset,
                    recommendation=f"{rec['reason']}. {rec['performance_gain']}"
                ))

        return issues

    def _recommend_recordsize(self, dataset: str, profile: str) -> ValidationIssue:
        """Recommend optimal recordsize for a profile."""
        if profile not in self.RECORDSIZE_RECOMMENDATIONS:
            return ValidationIssue(
                Severity.INFO,
                f"Unknown profile '{profile}' for recordsize recommendation",
                dataset=dataset
            )

        rec = self.RECORDSIZE_RECOMMENDATIONS[profile]
        return ValidationIssue(
            Severity.INFO,
            f"Recommend recordsize={rec['optimal']} for {dataset} ({profile})",
            dataset=dataset,
            recommendation=f"{rec['reason']}. {rec['performance_gain']}"
        )

    def _validate_compression(self, dataset: str, compression: str,
                            profile: Optional[str]) -> List[ValidationIssue]:
        """Validate compression setting."""
        issues = []

        # Valid compression algorithms
        valid = ['on', 'off', 'lz4', 'lzjb', 'gzip', 'gzip-1', 'gzip-9',
                'zstd', 'zstd-1', 'zstd-3', 'zstd-9', 'zstd-19']

        if compression not in valid:
            issues.append(ValidationIssue(
                Severity.ERROR,
                f"Invalid compression algorithm '{compression}'",
                dataset=dataset,
                recommendation=f"Valid options: {', '.join(valid)}"
            ))
            return issues

        # Check against profile
        if profile and profile in self.COMPRESSION_RECOMMENDATIONS:
            rec = self.COMPRESSION_RECOMMENDATIONS[profile]
            optimal = rec['optimal']

            if compression != optimal and compression not in rec.get('alternatives', []):
                issues.append(ValidationIssue(
                    Severity.INFO,
                    f"Compression {compression} may not be optimal for {profile}",
                    dataset=dataset,
                    recommendation=(
                        f"Consider {optimal} - {rec['reason']} "
                        f"(CPU impact: {rec['cpu_impact']})"
                    )
                ))

        # Warn about CPU-intensive compression
        if compression in ['gzip-9', 'zstd-9', 'zstd-19']:
            if profile not in ['backups']:
                issues.append(ValidationIssue(
                    Severity.WARNING,
                    f"High CPU compression ({compression}) on {dataset}",
                    dataset=dataset,
                    recommendation="This will slow down writes significantly. Use for backups only."
                ))

        return issues

    def _recommend_compression(self, dataset: str, profile: str) -> ValidationIssue:
        """Recommend optimal compression for a profile."""
        if profile not in self.COMPRESSION_RECOMMENDATIONS:
            return ValidationIssue(
                Severity.INFO,
                f"Unknown profile '{profile}' for compression recommendation",
                dataset=dataset
            )

        rec = self.COMPRESSION_RECOMMENDATIONS[profile]
        msg = f"Recommend compression={rec['optimal']} for {dataset} ({profile})"
        rec_text = f"{rec['reason']}. CPU impact: {rec['cpu_impact']}"

        if 'space_savings' in rec:
            rec_text += f". {rec['space_savings']}"

        return ValidationIssue(
            Severity.INFO,
            msg,
            dataset=dataset,
            recommendation=rec_text
        )

    @staticmethod
    def _parse_size(size_str: str) -> int:
        """Parse size string like '1M', '128K' to bytes."""
        size_str = size_str.upper().strip()

        multipliers = {
            'K': 1024,
            'M': 1024 * 1024,
            'G': 1024 * 1024 * 1024
        }

        if size_str[-1] in multipliers:
            return int(size_str[:-1]) * multipliers[size_str[-1]]
        else:
            return int(size_str)

    def check_cross_pool_hardlinks(self, pools: Dict) -> List[ValidationIssue]:
        """Check for cross-pool hardlink issues.

        Args:
            pools: Dict of pool configurations

        Returns:
            List of validation issues
        """
        issues = []

        # Track which pool each container uses
        container_pools = {}  # container_name -> set of pool names

        for pool_name, pool_config in pools.items():
            if 'datasets' not in pool_config:
                continue

            for dataset_name, dataset_config in pool_config['datasets'].items():
                if 'containers' not in dataset_config:
                    continue

                for container in dataset_config['containers']:
                    # Get container name
                    if isinstance(container, dict):
                        name = container.get('name')
                    elif isinstance(container, str):
                        name = container.split(':')[0] if ':' in container else container
                    else:
                        continue

                    if not name:
                        continue

                    if name not in container_pools:
                        container_pools[name] = set()

                    container_pools[name].add(pool_name)

        # Check *arr apps specifically
        arr_apps = ['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr']

        for arr_app in arr_apps:
            if arr_app in container_pools and len(container_pools[arr_app]) > 1:
                pools_used = ', '.join(sorted(container_pools[arr_app]))
                issues.append(ValidationIssue(
                    Severity.ERROR,
                    f"Container '{arr_app}' uses multiple pools: {pools_used}",
                    recommendation=(
                        f"{arr_app} needs downloads + media on SAME pool for hardlinks! "
                        "Cross-pool moves will COPY files (slow, uses 2x space). "
                        "Move all datasets to the same pool."
                    )
                ))

        return issues

    def check_resource_allocation(self, dataset_name: str,
                                 containers: List[Dict],
                                 profile: Optional[str]) -> List[ValidationIssue]:
        """Check if container resources are appropriate.

        Args:
            dataset_name: Dataset name
            containers: List of container configs
            profile: Dataset profile

        Returns:
            List of validation issues
        """
        issues = []

        # Resource recommendations by app
        app_requirements = {
            'jellyfin': {
                'min_memory': 2048,
                'recommended_memory': 4096,
                'min_cores': 2,
                'recommended_cores': 4,
                'note': '8GB+ RAM and 8+ cores for 4K transcoding'
            },
            'immich': {
                'min_memory': 4096,
                'recommended_memory': 8192,
                'min_cores': 2,
                'recommended_cores': 4,
                'note': 'AI features need 4GB+, more for large photo libraries'
            },
            'nextcloud': {
                'min_memory': 2048,
                'recommended_memory': 4096,
                'min_cores': 2,
                'recommended_cores': 4,
                'note': '4GB+ recommended for multiple users'
            },
            'homeassistant': {
                'min_memory': 2048,
                'recommended_memory': 4096,
                'min_cores': 2,
                'recommended_cores': 4,
                'note': '4GB handles 100+ devices'
            },
            'ollama': {
                'min_memory': 8192,
                'recommended_memory': 16384,
                'min_cores': 4,
                'recommended_cores': 8,
                'note': '8GB for 7B models, 16GB for 13B, 32GB+ for 70B'
            }
        }

        for container in containers:
            if not isinstance(container, dict):
                continue

            name = container.get('name', '').lower()
            memory = container.get('memory')
            cores = container.get('cores')

            # Check against requirements
            for app, reqs in app_requirements.items():
                if app in name:
                    # Check memory
                    if memory and memory < reqs['min_memory']:
                        issues.append(ValidationIssue(
                            Severity.WARNING,
                            f"Container '{name}' has {memory}MB RAM, needs {reqs['min_memory']}MB minimum",
                            dataset=dataset_name,
                            recommendation=f"{reqs['note']}"
                        ))
                    elif memory and memory < reqs['recommended_memory']:
                        issues.append(ValidationIssue(
                            Severity.INFO,
                            f"Container '{name}' has {memory}MB RAM, {reqs['recommended_memory']}MB recommended",
                            dataset=dataset_name,
                            recommendation=reqs['note']
                        ))

                    # Check cores
                    if cores and cores < reqs['min_cores']:
                        issues.append(ValidationIssue(
                            Severity.WARNING,
                            f"Container '{name}' has {cores} cores, needs {reqs['min_cores']} minimum",
                            dataset=dataset_name,
                            recommendation=reqs['note']
                        ))

        return issues
