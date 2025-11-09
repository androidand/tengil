"""Tests for snapshot and recovery functionality."""
import pytest
from tengil.core.snapshot_manager import SnapshotManager
from tengil.core.recovery import RecoveryManager


class TestSnapshotManager:
    """Test snapshot management."""

    def test_create_snapshot_mock(self):
        """Test snapshot creation in mock mode."""
        sm = SnapshotManager(mock=True)
        datasets = ['tank/media', 'tank/downloads']

        created = sm.create_snapshot(datasets, name='test')

        assert len(created) == 2
        assert 'tank/media' in created
        assert 'tank/downloads' in created
        assert 'tengil_test' in created['tank/media']

    def test_list_snapshots_mock(self):
        """Test listing snapshots in mock mode."""
        sm = SnapshotManager(mock=True)

        snapshots = sm.list_snapshots()

        assert len(snapshots) == 1
        assert snapshots[0]['dataset'] == 'tank/media'
        assert snapshots[0]['name'] == 'tengil_20250109_120000'

    def test_rollback_mock(self):
        """Test rollback in mock mode."""
        sm = SnapshotManager(mock=True)

        result = sm.rollback('tank/media', 'tengil_20250109_120000', force=True)

        assert result is True

    def test_cleanup_snapshots_mock(self):
        """Test cleanup in mock mode."""
        sm = SnapshotManager(mock=True)

        # Cleanup returns 0 in mock since we only have 1 snapshot
        deleted = sm.cleanup_old_snapshots(keep=5)

        assert deleted == 0

    def test_destroy_snapshot_mock(self):
        """Test destroy snapshot in mock mode."""
        sm = SnapshotManager(mock=True)

        result = sm.destroy_snapshot('tank/media@tengil_20250109_120000')

        assert result is True

    def test_get_snapshot_size_mock(self):
        """Test getting snapshot size in mock mode."""
        sm = SnapshotManager(mock=True)

        size = sm.get_snapshot_size('tank/media@tengil_20250109_120000')

        assert size == "1.2M"


class TestRecoveryManager:
    """Test recovery and checkpoint functionality."""

    def test_create_checkpoint_no_datasets(self):
        """Test checkpoint creation without datasets."""
        rm = RecoveryManager(mock=True)

        checkpoint = rm.create_checkpoint()

        assert 'timestamp' in checkpoint
        assert 'datasets' in checkpoint
        assert checkpoint['datasets'] == []
        assert 'snapshots' in checkpoint
        assert checkpoint['snapshots'] == {}

    def test_create_checkpoint_with_datasets(self):
        """Test checkpoint creation with datasets."""
        rm = RecoveryManager(mock=True)
        datasets = ['tank/media', 'tank/downloads']

        checkpoint = rm.create_checkpoint(datasets, name='backup')

        assert checkpoint['datasets'] == datasets
        assert len(checkpoint['snapshots']) == 2
        assert 'tank/media' in checkpoint['snapshots']

    def test_rollback_checkpoint(self):
        """Test rollback from checkpoint."""
        rm = RecoveryManager(mock=True)
        datasets = ['tank/media']

        checkpoint = rm.create_checkpoint(datasets, name='test')
        result = rm.rollback(checkpoint)

        assert result is True

    def test_backup_methods_mock(self):
        """Test config backup methods in mock mode."""
        rm = RecoveryManager(mock=True)

        storage_backup = rm.backup_storage_cfg()
        smb_backup = rm.backup_smb_conf()

        # In mock mode without files, should return mock paths
        assert storage_backup is None or 'mock' in storage_backup
        assert smb_backup is None or 'mock' in smb_backup

    def test_restore_file_mock(self):
        """Test file restoration in mock mode."""
        rm = RecoveryManager(mock=True)

        result = rm.restore_file('/backup/test.cfg', '/etc/test.cfg')

        assert result is True

    def test_checkpoint_with_name(self):
        """Test checkpoint with custom name."""
        rm = RecoveryManager(mock=True)
        datasets = ['tank/media']

        checkpoint = rm.create_checkpoint(datasets, name='custom-backup')

        assert 'custom-backup' in checkpoint['snapshots']['tank/media']

    def test_rollback_without_snapshots(self):
        """Test rollback checkpoint without snapshots."""
        rm = RecoveryManager(mock=True)

        checkpoint = rm.create_checkpoint()  # No datasets
        result = rm.rollback(checkpoint)

        assert result is True

    def test_snapshot_create_with_name(self):
        """Test snapshot creation with custom name."""
        sm = SnapshotManager(mock=True)

        created = sm.create_snapshot(['tank/media'], name='mybackup')

        assert 'mybackup' in created['tank/media']

    def test_snapshot_list_filtering(self):
        """Test snapshot listing with dataset filter."""
        sm = SnapshotManager(mock=True)

        snapshots = sm.list_snapshots(dataset='tank/media')

        assert len(snapshots) == 1
        assert snapshots[0]['dataset'] == 'tank/media'
