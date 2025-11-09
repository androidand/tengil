"""Recovery and rollback functionality."""
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
from tengil.core.logger import get_logger
from tengil.core.snapshot_manager import SnapshotManager

logger = get_logger(__name__)


class RecoveryManager:
    """Rollback capability for when things go wrong."""

    def __init__(self, mock: bool = False):
        self.checkpoints = []
        self.mock = mock
        self.backup_dir = Path("/var/lib/tengil/backups")
        self.snapshot_manager = SnapshotManager(mock=mock)

    def create_checkpoint(self, datasets: List[str] = None, name: str = None) -> Dict:
        """Snapshot current state before changes.

        Args:
            datasets: Optional list of datasets to snapshot
            name: Optional name for snapshots

        Returns:
            Checkpoint dictionary with timestamp and backup info
        """
        timestamp = datetime.now().isoformat()

        # Create ZFS snapshots if datasets provided
        snapshots = {}
        if datasets:
            snapshots = self.snapshot_manager.create_snapshot(datasets, name=name)

        checkpoint = {
            'timestamp': timestamp,
            'datasets': datasets or [],
            'snapshots': snapshots,
            'storage_cfg': self.backup_storage_cfg(),
            'smb_conf': self.backup_smb_conf()
        }
        self.checkpoints.append(checkpoint)
        logger.info(f"Created checkpoint at {timestamp}")
        return checkpoint

    def snapshot_datasets(self):
        """Take snapshot of current dataset state.

        DEPRECATED: Snapshots are now handled by SnapshotManager.
        This method is kept for backwards compatibility.
        """
        return {}

    def backup_storage_cfg(self) -> Optional[str]:
        """Backup Proxmox storage configuration.

        Returns:
            Path to backup file, or None if storage.cfg doesn't exist
        """
        storage_cfg = Path("/etc/pve/storage.cfg")

        if not storage_cfg.exists():
            logger.debug("storage.cfg not found, skipping backup")
            return None

        if self.mock:
            logger.info("MOCK: Would backup storage.cfg")
            return "/var/lib/tengil/backups/storage.cfg.mock"

        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = self.backup_dir / f"storage.cfg.{timestamp}"

        try:
            shutil.copy2(storage_cfg, backup_file)
            logger.info(f"Backed up storage.cfg to {backup_file}")
            return str(backup_file)
        except (IOError, OSError) as e:
            logger.error(f"Failed to backup storage.cfg: {e}")
            return None

    def backup_smb_conf(self) -> Optional[str]:
        """Backup Samba configuration.

        Returns:
            Path to backup file, or None if smb.conf doesn't exist
        """
        smb_conf = Path("/etc/samba/smb.conf")

        if not smb_conf.exists():
            logger.debug("smb.conf not found, skipping backup")
            return None

        if self.mock:
            logger.info("MOCK: Would backup smb.conf")
            return "/var/lib/tengil/backups/smb.conf.mock"

        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = self.backup_dir / f"smb.conf.{timestamp}"

        try:
            shutil.copy2(smb_conf, backup_file)
            logger.info(f"Backed up smb.conf to {backup_file}")
            return str(backup_file)
        except (IOError, OSError) as e:
            logger.error(f"Failed to backup smb.conf: {e}")
            return None

    def restore_file(self, backup_path: str, target_path: str) -> bool:
        """Restore a backed up configuration file.

        Args:
            backup_path: Path to backup file
            target_path: Target path to restore to

        Returns:
            True if successful, False otherwise
        """
        if self.mock:
            logger.info(f"MOCK: Would restore {target_path} from {backup_path}")
            return True

        try:
            shutil.copy2(backup_path, target_path)
            logger.info(f"Restored {target_path} from {backup_path}")
            return True
        except (IOError, OSError) as e:
            logger.error(f"Failed to restore {target_path}: {e}")
            return False

    def rollback(self, checkpoint: Dict, force: bool = True) -> bool:
        """Restore to checkpoint if apply fails.

        Args:
            checkpoint: Checkpoint dictionary from create_checkpoint()
            force: Force ZFS rollback (destroys newer snapshots)

        Returns:
            True if rollback successful
        """
        logger.warning(f"Rolling back to {checkpoint['timestamp']}")

        success = True

        # Rollback ZFS snapshots first
        if checkpoint.get('snapshots'):
            for dataset, snapshot_name in checkpoint['snapshots'].items():
                logger.info(f"Rolling back {dataset} to {snapshot_name}")
                if not self.snapshot_manager.rollback(dataset, snapshot_name, force=force):
                    logger.error(f"Failed to rollback {dataset}")
                    success = False

        # Restore config files
        if checkpoint.get('storage_cfg'):
            if not self.restore_file(checkpoint['storage_cfg'], "/etc/pve/storage.cfg"):
                success = False

        if checkpoint.get('smb_conf'):
            if not self.restore_file(checkpoint['smb_conf'], "/etc/samba/smb.conf"):
                success = False

        if success:
            logger.info("Rollback complete")
        else:
            logger.warning("Rollback completed with errors")

        return success
