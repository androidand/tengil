"""Tests for Phase 1 Task 3: Mount existing containers."""
from tengil.services.proxmox.manager import ProxmoxManager


class TestMountExistingContainers:
    """Test mounting datasets to existing containers."""

    def test_mount_by_name(self):
        """Test mounting dataset by container name."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': [
                {'name': 'jellyfin', 'mount': '/media'}
            ]
        }
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        assert len(results) == 1
        vmid, success, msg = results[0]
        assert vmid == 100  # jellyfin is vmid 100 in mock
        assert success is True
        assert msg in ['mounted', 'already exists']

    def test_mount_by_vmid(self):
        """Test mounting dataset by container vmid."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': [
                {'vmid': 100, 'mount': '/media'}
            ]
        }
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        assert len(results) == 1
        vmid, success, msg = results[0]
        assert vmid == 100
        assert success is True

    def test_mount_string_format(self):
        """Test mounting with string format."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': ['jellyfin:/media']
        }
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        assert len(results) == 1
        vmid, success, msg = results[0]
        assert vmid == 100
        assert success is True

    def test_mount_string_format_readonly(self):
        """Test mounting with readonly string format."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': ['jellyfin:/media:ro']
        }
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        assert len(results) == 1
        vmid, success, msg = results[0]
        assert vmid == 100
        assert success is True

    def test_mount_nonexistent_container_by_name(self):
        """Test mounting to nonexistent container by name."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': [
                {'name': 'nonexistent', 'mount': '/media'}
            ]
        }
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        assert len(results) == 1
        vmid, success, msg = results[0]
        assert vmid == 0  # No vmid found
        assert success is False
        assert 'not found' in msg.lower()

    def test_mount_multiple_containers(self):
        """Test mounting to multiple containers."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': [
                {'name': 'jellyfin', 'mount': '/media'},
                {'name': 'nextcloud', 'mount': '/data'},
                {'vmid': 100, 'mount': '/backup'}
            ]
        }
        
        results = pm.containers.setup_container_mounts('storage', dataset_config, 'tank')
        
        assert len(results) == 3
        
        # All should succeed (jellyfin=100, nextcloud=101)
        assert all(success for _, success, _ in results)
        
        # Check vmids
        vmids = [vmid for vmid, _, _ in results]
        assert 100 in vmids  # jellyfin
        assert 101 in vmids  # nextcloud

    def test_mount_with_readonly_flag(self):
        """Test mounting with readonly flag."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': [
                {'name': 'jellyfin', 'mount': '/media', 'readonly': True}
            ]
        }
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        assert len(results) == 1
        vmid, success, msg = results[0]
        assert success is True

    def test_auto_create_containers(self):
        """Test that auto_create containers are created and mounted (Phase 2)."""
        pm = ProxmoxManager(mock=True)

        dataset_config = {
            'containers': [
                {
                    'name': 'jellyfin',
                    'vmid': 200,
                    'auto_create': True,
                    'template': 'debian-12-standard',
                    'mount': '/media'
                }
            ]
        }

        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')

        assert len(results) == 1
        vmid, success, msg = results[0]
        assert vmid == 200  # Container created with specified VMID
        assert success is True  # Mount succeeded
        assert 'mounted' in msg.lower() or 'already exists' in msg.lower()

    def test_mount_mixed_formats(self):
        """Test mixing different container specification formats."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': [
                'jellyfin:/media',  # String format
                {'name': 'nextcloud', 'mount': '/data'},  # Dict with name
                {'vmid': 100, 'mount': '/backup', 'readonly': True}  # Dict with vmid
            ]
        }
        
        results = pm.containers.setup_container_mounts('storage', dataset_config, 'tank')
        
        assert len(results) == 3
        assert all(success for _, success, _ in results)

    def test_idempotent_mount_detection(self):
        """Test that mounts are idempotent (detected when already exist)."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': [
                {'name': 'jellyfin', 'mount': '/media'}
            ]
        }
        
        # First mount
        results1 = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        assert len(results1) == 1
        assert results1[0][1] is True  # Success
        
        # Second mount (should detect existing mount - but in mock it won't)
        # In real implementation with proper state, this would show "already exists"
        results2 = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        assert len(results2) == 1
        assert results2[0][1] is True  # Still success


class TestContainerMountValidation:
    """Test validation of container mount specifications."""

    def test_invalid_container_spec_type(self):
        """Test handling of invalid container spec types."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': [
                123,  # Invalid: not string or dict
            ]
        }
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        assert len(results) == 1
        vmid, success, msg = results[0]
        assert success is False
        assert 'invalid' in msg.lower()

    def test_empty_containers_list(self):
        """Test handling of empty containers list."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': []
        }
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        assert len(results) == 0

    def test_no_containers_key(self):
        """Test handling when containers key is missing."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {}
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        assert len(results) == 0

    def test_mount_path_defaults(self):
        """Test default mount path behavior."""
        pm = ProxmoxManager(mock=True)
        
        # Dict without mount path - should default to /dataset_name
        dataset_config = {
            'containers': [
                {'name': 'jellyfin'}  # No mount path specified
            ]
        }
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        assert len(results) == 1
        assert results[0][1] is True


class TestContainerMountResults:
    """Test the structure and content of mount operation results."""

    def test_result_tuple_structure(self):
        """Results should be tuples of (vmid, success, message)."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': [
                {'name': 'jellyfin', 'mount': '/media'}
            ]
        }
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        assert len(results) == 1
        result = results[0]
        
        # Should be 3-tuple
        assert len(result) == 3
        
        vmid, success, msg = result
        assert isinstance(vmid, int)
        assert isinstance(success, bool)
        assert isinstance(msg, str)

    def test_success_messages(self):
        """Test that success messages are informative."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': [
                {'name': 'jellyfin', 'mount': '/media'}
            ]
        }
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        vmid, success, msg = results[0]
        assert success is True
        assert msg in ['mounted', 'already exists']

    def test_failure_messages(self):
        """Test that failure messages are informative."""
        pm = ProxmoxManager(mock=True)
        
        dataset_config = {
            'containers': [
                {'name': 'nonexistent', 'mount': '/media'}
            ]
        }
        
        results = pm.containers.setup_container_mounts('media', dataset_config, 'tank')
        
        vmid, success, msg = results[0]
        assert success is False
        assert len(msg) > 0
        assert 'not found' in msg.lower()
