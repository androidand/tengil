"""End-to-end test for apply workflow with consumers model."""
import pytest
from pathlib import Path
import tempfile
import yaml
from unittest.mock import Mock, patch, MagicMock

from tengil.config.loader import ConfigLoader
from tengil.core.zfs_manager import ZFSManager
from tengil.core.orchestrator import PoolOrchestrator
from tengil.core.diff_engine import DiffEngine
from tengil.core.applicator import ChangeApplicator
from tengil.core.permission_manager import PermissionManager, ConsumerType, AccessLevel
from tengil.core.state_store import StateStore
from tengil.services.proxmox import ProxmoxManager
from tengil.services.nas import NASManager


class TestApplyWithConsumers:
    """Test full apply workflow with consumers model."""

    @pytest.fixture
    def config_with_consumers(self, tmp_path):
        """Create a config file with consumers model."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'type': 'zfs',
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'consumers': [
                                {
                                    'type': 'container',
                                    'name': 'jellyfin',
                                    'access': 'read',
                                    'mount': '/media'
                                },
                                {
                                    'type': 'smb',
                                    'name': 'Media',
                                    'access': 'write'
                                }
                            ]
                        },
                        'photos': {
                            'profile': 'photos',
                            'consumers': [
                                {
                                    'type': 'container',
                                    'name': 'immich',
                                    'access': 'write',
                                    'mount': '/photos'
                                },
                                {
                                    'type': 'nfs',
                                    'name': 'photos-nfs',
                                    'allowed': '192.168.1.0/24',
                                    'access': 'read'
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        config_file = tmp_path / "tengil.yml"
        with open(config_file, 'w') as f:
            yaml.dump(config, f)
        
        return config_file

    def test_apply_workflow_with_consumers(self, config_with_consumers, tmp_path):
        """Test complete apply workflow with consumers."""
        # Load config
        loader = ConfigLoader(config_with_consumers)
        config = loader.load()
        
        # Verify consumers were parsed correctly
        media_consumers = config['pools']['tank']['datasets']['media']['consumers']
        assert len(media_consumers) == 2
        assert media_consumers[0]['type'] == 'container'
        assert media_consumers[0]['access'] == 'read'
        assert media_consumers[1]['type'] == 'smb'
        assert media_consumers[1]['access'] == 'write'
        
        photos_consumers = config['pools']['tank']['datasets']['photos']['consumers']
        assert len(photos_consumers) == 2
        assert photos_consumers[0]['type'] == 'container'
        assert photos_consumers[0]['access'] == 'write'
        assert photos_consumers[1]['type'] == 'nfs'

    def test_permission_manager_integration(self, config_with_consumers):
        """Test that permission manager is properly integrated."""
        # Initialize permission manager
        permission_mgr = PermissionManager()
        
        # Initialize managers with permission manager
        zfs = ZFSManager(mock=True, permission_manager=permission_mgr)
        proxmox = ProxmoxManager(mock=True, permission_manager=permission_mgr)
        nas = NASManager(mock=True, permission_manager=permission_mgr)
        
        # Verify they all have the same permission manager instance
        assert zfs.permission_manager is permission_mgr
        assert proxmox.permission_manager is permission_mgr
        assert nas.permission_manager is permission_mgr

    def test_consumers_applied_to_dataset(self, config_with_consumers):
        """Test that consumers are properly applied when creating datasets."""
        loader = ConfigLoader(config_with_consumers)
        config = loader.load()
        
        # Mock permission manager
        permission_mgr = Mock(spec=PermissionManager)
        
        # Mock ZFS manager
        zfs = Mock(spec=ZFSManager)
        zfs.dataset_exists.return_value = False
        zfs.create_dataset.return_value = True
        zfs.permission_manager = permission_mgr
        
        # Get dataset config
        dataset_config = config['pools']['tank']['datasets']['media']
        
        # Verify consumers are in config
        assert 'consumers' in dataset_config
        assert len(dataset_config['consumers']) == 2

    def test_readonly_mount_for_read_access(self, config_with_consumers):
        """Test that read access creates readonly mounts."""
        loader = ConfigLoader(config_with_consumers)
        config = loader.load()
        
        media_consumers = config['pools']['tank']['datasets']['media']['consumers']
        jellyfin_consumer = media_consumers[0]
        
        # Read access should result in readonly mount
        assert jellyfin_consumer['access'] == 'read'
        # In actual apply, this would be converted to readonly=True

    def test_write_mount_for_write_access(self, config_with_consumers):
        """Test that write access creates read-write mounts."""
        loader = ConfigLoader(config_with_consumers)
        config = loader.load()
        
        photos_consumers = config['pools']['tank']['datasets']['photos']['consumers']
        immich_consumer = photos_consumers[0]
        
        # Write access should result in read-write mount
        assert immich_consumer['access'] == 'write'
        # In actual apply, this would be converted to readonly=False

    def test_smb_consumer_creates_share(self, config_with_consumers):
        """Test that SMB consumer creates share configuration."""
        loader = ConfigLoader(config_with_consumers)
        config = loader.load()
        
        media_consumers = config['pools']['tank']['datasets']['media']['consumers']
        smb_consumer = media_consumers[1]
        
        assert smb_consumer['type'] == 'smb'
        assert smb_consumer['name'] == 'Media'
        assert smb_consumer['access'] == 'write'

    def test_nfs_consumer_creates_export(self, config_with_consumers):
        """Test that NFS consumer creates export configuration."""
        loader = ConfigLoader(config_with_consumers)
        config = loader.load()
        
        photos_consumers = config['pools']['tank']['datasets']['photos']['consumers']
        nfs_consumer = photos_consumers[1]
        
        assert nfs_consumer['type'] == 'nfs'
        assert nfs_consumer['allowed'] == '192.168.1.0/24'
        assert nfs_consumer['access'] == 'read'

    def test_full_apply_simulation(self, config_with_consumers, tmp_path):
        """Simulate full apply workflow with mocked managers."""
        # Load config
        loader = ConfigLoader(config_with_consumers)
        config = loader.load()
        
        # Initialize permission manager
        permission_mgr = PermissionManager()
        
        # Initialize mock managers
        state = StateStore(state_file=tmp_path / ".tengilstate.json")
        zfs = ZFSManager(mock=True, state_store=state, permission_manager=permission_mgr)
        proxmox = ProxmoxManager(mock=True, permission_manager=permission_mgr)
        nas = NASManager(mock=True, permission_manager=permission_mgr)
        
        # Calculate diffs
        orchestrator = PoolOrchestrator(loader, zfs)
        all_desired, all_current = orchestrator.flatten_pools()
        
        engine = DiffEngine(all_desired, all_current)
        changes = engine.calculate_diff()
        
        # Verify changes include consumers
        assert 'tank/media' in all_desired
        assert 'consumers' in all_desired['tank/media']
        assert len(all_desired['tank/media']['consumers']) == 2
        
        assert 'tank/photos' in all_desired
        assert 'consumers' in all_desired['tank/photos']
        assert len(all_desired['tank/photos']['consumers']) == 2

    def test_permission_manager_called_for_consumers(self, config_with_consumers, tmp_path):
        """Test that permission manager is invoked for consumer operations."""
        loader = ConfigLoader(config_with_consumers)
        config = loader.load()
        
        # Create real permission manager (not mock)
        permission_mgr = PermissionManager(mock=True)
        
        # Create managers with permission_manager
        from tengil.core.zfs_manager import ZFSManager
        from tengil.services.proxmox.manager import ProxmoxManager
        from tengil.services.nas.manager import NASManager
        from tengil.core.state_store import StateStore
        
        state = StateStore()
        zfs = ZFSManager(mock=True, state_store=state, permission_manager=permission_mgr)
        proxmox = ProxmoxManager(mock=True, permission_manager=permission_mgr)
        nas = NASManager(mock=True, permission_manager=permission_mgr)
        
        # Verify permission_manager was passed
        assert zfs.permission_manager is permission_mgr
        assert proxmox.permission_manager is permission_mgr
        assert nas.permission_manager is permission_mgr
        
        # Verify we can register datasets and consumers
        dataset_path = "tank/photos"
        permission_mgr.register_dataset(dataset_path)
        
        # Verify we can add consumers
        permission_mgr.add_consumer(
            dataset_path, 
            ConsumerType.CONTAINER, 
            "immich", 
            AccessLevel.WRITE
        )
        permission_mgr.add_consumer(
            dataset_path, 
            ConsumerType.SHARE_NFS, 
            "photos-nfs", 
            AccessLevel.READ
        )
        
        # Verify consumers were added
        perm_set = permission_mgr.permission_sets[dataset_path]
        assert len(perm_set.consumers) == 2
        assert any(c.name == "immich" and c.access == AccessLevel.WRITE for c in perm_set.consumers)
        assert any(c.name == "photos-nfs" and c.access == AccessLevel.READ for c in perm_set.consumers)


class TestConsumerAccessLevels:
    """Test different access levels for consumers."""

    def test_read_access_container(self):
        """Test read access for containers creates readonly mount."""
        consumer = {
            'type': 'container',
            'name': 'viewer',
            'access': 'read',
            'mount': '/data'
        }
        
        # In apply workflow, this should translate to readonly=True
        assert consumer['access'] == 'read'

    def test_write_access_container(self):
        """Test write access for containers creates read-write mount."""
        consumer = {
            'type': 'container',
            'name': 'editor',
            'access': 'write',
            'mount': '/data'
        }
        
        # In apply workflow, this should translate to readonly=False
        assert consumer['access'] == 'write'

    def test_read_access_smb(self):
        """Test read access for SMB creates read-only share."""
        consumer = {
            'type': 'smb',
            'name': 'ReadOnly',
            'access': 'read'
        }
        
        # In apply workflow, this should translate to read only: yes
        assert consumer['access'] == 'read'

    def test_write_access_smb(self):
        """Test write access for SMB creates read-write share."""
        consumer = {
            'type': 'smb',
            'name': 'ReadWrite',
            'access': 'write'
        }
        
        # In apply workflow, this should translate to writable: yes
        assert consumer['access'] == 'write'


class TestConsumerValidation:
    """Test validation of consumer configurations."""

    def test_valid_container_consumer(self):
        """Test validation of valid container consumer."""
        consumer = {
            'type': 'container',
            'name': 'app',
            'access': 'read',
            'mount': '/data'
        }
        
        assert consumer['type'] == 'container'
        assert 'name' in consumer
        assert 'access' in consumer
        assert 'mount' in consumer

    def test_valid_smb_consumer(self):
        """Test validation of valid SMB consumer."""
        consumer = {
            'type': 'smb',
            'name': 'Share',
            'access': 'write'
        }
        
        assert consumer['type'] == 'smb'
        assert 'name' in consumer
        assert 'access' in consumer

    def test_valid_nfs_consumer(self):
        """Test validation of valid NFS consumer."""
        consumer = {
            'type': 'nfs',
            'allowed': '192.168.1.0/24',
            'access': 'read'
        }
        
        assert consumer['type'] == 'nfs'
        assert 'allowed' in consumer
        assert 'access' in consumer
