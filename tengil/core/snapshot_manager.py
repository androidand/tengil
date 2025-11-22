"""ZFS snapshot management for rollback capability."""
import subprocess
from datetime import datetime
from typing import Dict, List

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class SnapshotManager:
    """Manage ZFS snapshots for safe rollback."""

    def __init__(self, mock: bool = False):
        self.mock = mock
        self.snapshot_prefix = "tengil"

    def create_snapshot(self, datasets: List[str], name: str = None) -> Dict[str, str]:
        """Create snapshots for datasets.

        Args:
            datasets: List of dataset paths (pool/dataset)
            name: Optional snapshot name (auto-generated if None)

        Returns:
            Dict mapping dataset -> snapshot_name
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        snapshot_name = f"{self.snapshot_prefix}_{name}_{timestamp}" if name else f"{self.snapshot_prefix}_{timestamp}"

        created = {}
        for dataset in datasets:
            full_snapshot = f"{dataset}@{snapshot_name}"

            if not self.mock:
                try:
                    cmd = ["zfs", "snapshot", full_snapshot]
                    subprocess.run(cmd, check=True, capture_output=True)
                    logger.info(f"Created snapshot: {full_snapshot}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to create snapshot {full_snapshot}: {e}")
                    continue
            else:
                logger.info(f"MOCK: Would create snapshot {full_snapshot}")

            created[dataset] = snapshot_name

        return created

    def list_snapshots(self, dataset: str = None) -> List[Dict]:
        """List tengil-managed snapshots.

        Args:
            dataset: Optional dataset filter (pool/dataset)

        Returns:
            List of snapshot info dicts
        """
        if self.mock:
            return [
                {
                    'snapshot': 'tank/media@tengil_20250109_120000',
                    'dataset': 'tank/media',
                    'name': 'tengil_20250109_120000',
                    'created': '2025-01-09 12:00:00',
                    'used': '1.2M'
                }
            ]

        cmd = ["zfs", "list", "-t", "snapshot", "-H", "-o", "name,creation,used"]
        if dataset:
            cmd.extend(["-r", dataset])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list snapshots: {e}")
            return []

        snapshots = []
        for line in result.stdout.splitlines():
            parts = line.split('\t')
            if len(parts) < 3:
                continue

            full_name = parts[0]
            # Only include tengil-managed snapshots
            if self.snapshot_prefix not in full_name:
                continue

            if '@' not in full_name:
                continue

            dataset_name, snapshot_name = full_name.split('@')
            snapshots.append({
                'snapshot': full_name,
                'dataset': dataset_name,
                'name': snapshot_name,
                'created': parts[1],
                'used': parts[2]
            })

        return snapshots

    def rollback(self, dataset: str, snapshot_name: str, force: bool = False) -> bool:
        """Rollback dataset to snapshot.

        Args:
            dataset: Dataset path (pool/dataset)
            snapshot_name: Snapshot name (without @)
            force: Force rollback, destroying newer snapshots

        Returns:
            True if successful
        """
        full_snapshot = f"{dataset}@{snapshot_name}"

        if self.mock:
            logger.info(f"MOCK: Would rollback to {full_snapshot}")
            return True

        try:
            cmd = ["zfs", "rollback"]
            if force:
                cmd.append("-r")  # Recursive, destroy newer snapshots
            cmd.append(full_snapshot)

            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Rolled back to {full_snapshot}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to rollback to {full_snapshot}: {e}")
            return False

    def cleanup_old_snapshots(self, keep: int = 5) -> int:
        """Remove old tengil snapshots, keeping latest N.

        Args:
            keep: Number of snapshots to keep per dataset

        Returns:
            Number of snapshots deleted
        """
        # Group snapshots by dataset
        all_snapshots = self.list_snapshots()
        by_dataset = {}

        for snap in all_snapshots:
            dataset = snap['dataset']
            if dataset not in by_dataset:
                by_dataset[dataset] = []
            by_dataset[dataset].append(snap)

        deleted_count = 0
        for dataset, snapshots in by_dataset.items():
            # Sort by name (which includes timestamp)
            snapshots.sort(key=lambda x: x['name'], reverse=True)

            # Delete old snapshots
            for snap in snapshots[keep:]:
                if not self.mock:
                    try:
                        cmd = ["zfs", "destroy", snap['snapshot']]
                        subprocess.run(cmd, check=True, capture_output=True)
                        logger.info(f"Deleted snapshot: {snap['snapshot']}")
                        deleted_count += 1
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to delete {snap['snapshot']}: {e}")
                else:
                    logger.info(f"MOCK: Would delete {snap['snapshot']}")
                    deleted_count += 1

        return deleted_count

    def get_snapshot_size(self, snapshot: str) -> str:
        """Get size of snapshot.

        Args:
            snapshot: Full snapshot name (dataset@snapshot)

        Returns:
            Size string (e.g., "1.2M")
        """
        if self.mock:
            return "1.2M"

        try:
            cmd = ["zfs", "get", "-H", "-o", "value", "used", snapshot]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get snapshot size: {e}")
            return "unknown"

    def destroy_snapshot(self, snapshot: str) -> bool:
        """Destroy a specific snapshot.

        Args:
            snapshot: Full snapshot name (dataset@snapshot)

        Returns:
            True if successful
        """
        if self.mock:
            logger.info(f"MOCK: Would destroy snapshot {snapshot}")
            return True

        try:
            cmd = ["zfs", "destroy", snapshot]
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Destroyed snapshot: {snapshot}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to destroy snapshot {snapshot}: {e}")
            return False
