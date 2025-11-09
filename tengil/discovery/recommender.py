"""Pool and dataset recommendation engine."""
import subprocess
from typing import Dict, List, Optional

from tengil.models.disk import PhysicalDisk
from tengil.models.pool import ZFSPool


class PoolRecommender:
    """Generate opinionated pool and dataset recommendations."""

    def __init__(self, disks: List[PhysicalDisk], pools: List[ZFSPool], mock: bool = False):
        self.disks = disks
        self.pools = pools
        self.mock = mock or (pools and any(p.mock for p in pools))

    def recommend_structure(self, use_cases: Optional[List[str]] = None) -> Dict:
        """Generate recommended pool structure based on available hardware.

        Args:
            use_cases: List of use cases like 'media-server', 'arr-stack', 'databases'
        """
        recommendations = {
            'pools': {},
            'reasoning': [],
            'warnings': []
        }

        # Auto-detect use cases if not provided
        if use_cases is None:
            use_cases = self._detect_use_cases()

        # Find fast and slow pools
        fast_pool = self._find_fast_pool()
        bulk_pool = self._find_bulk_pool()

        if not fast_pool and not bulk_pool:
            recommendations['warnings'].append(
                "No ZFS pools found. Run 'zpool create' to create pools first."
            )
            return recommendations

        # Generate recommendations for each pool
        if fast_pool:
            recommendations['pools'][fast_pool.name] = self._recommend_fast_pool_datasets(
                fast_pool, use_cases
            )

            if fast_pool.is_os_pool:
                recommendations['reasoning'].append(
                    f"'{fast_pool.name}' is your OS pool - using 'tengil' namespace for safety"
                )

        if bulk_pool:
            recommendations['pools'][bulk_pool.name] = self._recommend_bulk_pool_datasets(
                bulk_pool, use_cases
            )
            recommendations['reasoning'].append(
                f"'{bulk_pool.name}' is bulk storage - using for media and backups"
            )

        return recommendations

    def _find_fast_pool(self) -> Optional[ZFSPool]:
        """Find the fast pool (NVMe/SSD)."""
        # Prefer OS pools on NVMe
        for pool in self.pools:
            if pool.is_os_pool:
                return pool

        # Otherwise, find smallest pool (usually fast boot drive)
        if self.pools:
            return min(self.pools, key=lambda p: p.size_bytes)

        return None

    def _find_bulk_pool(self) -> Optional[ZFSPool]:
        """Find the bulk storage pool."""
        # Largest non-OS pool
        bulk_pools = [p for p in self.pools if not p.is_os_pool]
        if bulk_pools:
            return max(bulk_pools, key=lambda p: p.size_bytes)
        return None

    def _detect_use_cases(self) -> List[str]:
        """Auto-detect likely use cases from existing datasets."""
        if self.mock:
            # In mock mode, return empty list (no existing datasets)
            return []

        use_cases = set()

        for pool in self.pools:
            try:
                result = subprocess.run(
                    ['zfs', 'list', '-H', '-o', 'name', '-r', pool.name],
                    capture_output=True, text=True, check=True
                )
                datasets = result.stdout.lower()

                if any(word in datasets for word in ['media', 'movies', 'tv', 'plex', 'jellyfin']):
                    use_cases.add('media-server')

                if any(word in datasets for word in ['sonarr', 'radarr', 'lidarr', 'download']):
                    use_cases.add('arr-stack')

                if any(word in datasets for word in ['postgres', 'mysql', 'database', 'db']):
                    use_cases.add('databases')

            except subprocess.CalledProcessError:
                pass

        return list(use_cases)

    def _recommend_fast_pool_datasets(self, pool: ZFSPool, use_cases: List[str]) -> Dict:
        """Recommend datasets for fast pool."""
        namespace = "tengil" if pool.is_os_pool else ""
        datasets = {}

        # Always recommend appdata
        datasets[self._path(namespace, "appdata")] = {
            'profile': 'dev',
            'description': 'Container configuration files'
        }

        # Databases if needed
        if 'databases' in use_cases:
            datasets[self._path(namespace, "databases")] = {
                'profile': 'dev',
                'description': 'PostgreSQL, MySQL, Redis, etc',
                'zfs': {
                    'recordsize': '8K',
                    'logbias': 'latency'
                }
            }

        # Cache if media server
        if 'media-server' in use_cases:
            datasets[self._path(namespace, "cache")] = {
                'profile': 'dev',
                'description': 'Plex/Jellyfin metadata and thumbnails',
                'zfs': {
                    'sync': 'disabled'  # Cache can handle data loss
                }
            }

        return datasets

    def _recommend_bulk_pool_datasets(self, pool: ZFSPool, use_cases: List[str]) -> Dict:
        """Recommend datasets for bulk storage pool."""
        datasets = {}

        # Media server structure
        if 'media-server' in use_cases or 'arr-stack' in use_cases:
            datasets['media/downloads'] = {
                'profile': 'media',
                'description': 'Download client workspace'
            }
            datasets['media/tv'] = {
                'profile': 'media',
                'description': 'TV show library'
            }
            datasets['media/movies'] = {
                'profile': 'media',
                'description': 'Movie library'
            }
            datasets['media/music'] = {
                'profile': 'audio',
                'description': 'Music collection'
            }
            datasets['media/photos'] = {
                'profile': 'photos',
                'description': 'Photo library'
            }

        # Always recommend backups
        datasets['backups'] = {
            'profile': 'backups',
            'description': 'System and data backups',
            'zfs': {
                'compression': 'zstd',
                'copies': 2
            }
        }

        return datasets

    def _path(self, namespace: str, dataset: str) -> str:
        """Build dataset path with optional namespace."""
        if namespace:
            return f"{namespace}/{dataset}"
        return dataset
