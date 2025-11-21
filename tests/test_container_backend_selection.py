"""Tests for automatic backend selection in ContainerOrchestrator."""
import unittest
from unittest.mock import Mock, patch, MagicMock
from tengil.services.proxmox.containers.orchestrator import ContainerOrchestrator


class TestBackendSelection(unittest.TestCase):
    """Test automatic detection of OCI vs LXC containers."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = ContainerOrchestrator(mock=True)
    
    def test_lxc_backend_selected_for_traditional_spec(self):
        """Traditional LXC spec should use LXC backend."""
        spec = {
            'name': 'test-lxc',
            'vmid': 200,
            'template': 'debian-12-standard',
            'memory': 512,
            'cores': 1,
        }
        
        with patch.object(self.orchestrator.lifecycle, 'create_container') as mock_lxc:
            mock_lxc.return_value = 200
            
            vmid = self.orchestrator.create_container(spec)
            
            # Should call LXC backend
            mock_lxc.assert_called_once()
            self.assertEqual(vmid, 200)
    
    def test_oci_backend_selected_for_type_oci(self):
        """Spec with 'type: oci' should use OCI backend."""
        spec = {
            'name': 'test-nginx',
            'type': 'oci',
            'vmid': 201,
            'oci': {
                'image': 'nginx',
                'tag': 'alpine',
            },
            'memory': 512,
            'cores': 1,
        }
        
        with patch.object(self.orchestrator, '_create_oci_container') as mock_oci:
            mock_oci.return_value = 201
            
            vmid = self.orchestrator.create_container(spec)
            
            # Should call OCI backend
            mock_oci.assert_called_once_with(spec, 'local-lvm', None)
            self.assertEqual(vmid, 201)
    
    def test_oci_backend_selected_for_oci_section(self):
        """Spec with 'oci' section should use OCI backend."""
        spec = {
            'name': 'test-redis',
            'vmid': 202,
            'oci': {
                'image': 'redis',
                'tag': 'alpine',
                'registry': 'docker.io',
            },
            'memory': 256,
        }
        
        with patch.object(self.orchestrator, '_create_oci_container') as mock_oci:
            mock_oci.return_value = 202
            
            vmid = self.orchestrator.create_container(spec)
            
            # Should call OCI backend
            mock_oci.assert_called_once()
            self.assertEqual(vmid, 202)
    
    def test_oci_backend_pulls_image_before_creation(self):
        """OCI backend should pull image before creating container."""
        spec = {
            'name': 'test-jellyfin',
            'type': 'oci',
            'vmid': 203,
            'oci': {
                'image': 'jellyfin/jellyfin',
                'tag': 'latest',
            },
            'memory': 4096,
            'cores': 4,
        }
        
        with patch.object(self.orchestrator.oci_backend, 'pull_image') as mock_pull, \
             patch.object(self.orchestrator.oci_backend, 'create_container') as mock_create:
            
            mock_pull.return_value = 'local:vztmpl/jellyfin-latest.tar'
            mock_create.return_value = 203
            
            vmid = self.orchestrator.create_container(spec, storage='tank')
            
            # Should pull image first
            mock_pull.assert_called_once_with('jellyfin/jellyfin', 'latest', None)
            
            # Then create container with template reference
            mock_create.assert_called_once_with(
                spec=spec,
                template='local:vztmpl/jellyfin-latest.tar',
                storage='tank',
                pool=None
            )
            
            self.assertEqual(vmid, 203)
    
    def test_oci_backend_handles_custom_registry(self):
        """OCI backend should handle custom registry parameter."""
        spec = {
            'name': 'test-custom',
            'type': 'oci',
            'vmid': 204,
            'oci': {
                'image': 'home-assistant/home-assistant',
                'tag': 'stable',
                'registry': 'ghcr.io',
            },
        }
        
        with patch.object(self.orchestrator.oci_backend, 'pull_image') as mock_pull, \
             patch.object(self.orchestrator.oci_backend, 'create_container') as mock_create:
            
            mock_pull.return_value = 'local:vztmpl/home-assistant-stable.tar'
            mock_create.return_value = 204
            
            self.orchestrator.create_container(spec)
            
            # Should pass registry to pull_image
            mock_pull.assert_called_once_with('home-assistant/home-assistant', 'stable', 'ghcr.io')
    
    def test_oci_backend_fails_gracefully_on_missing_image(self):
        """OCI backend should return None if image field is missing."""
        spec = {
            'name': 'test-broken',
            'type': 'oci',
            'vmid': 205,
            'oci': {
                'tag': 'latest',  # Missing 'image' field
            },
        }
        
        vmid = self.orchestrator.create_container(spec)
        
        # Should return None for invalid spec
        self.assertIsNone(vmid)
    
    def test_oci_backend_fails_gracefully_on_pull_failure(self):
        """OCI backend should return None if image pull fails."""
        spec = {
            'name': 'test-nonexistent',
            'type': 'oci',
            'vmid': 206,
            'oci': {
                'image': 'nonexistent/fakeimage',
                'tag': 'latest',
            },
        }
        
        with patch.object(self.orchestrator.oci_backend, 'pull_image') as mock_pull:
            mock_pull.return_value = None  # Simulate pull failure
            
            vmid = self.orchestrator.create_container(spec)
            
            # Should return None on pull failure
            self.assertIsNone(vmid)
    
    def test_storage_and_pool_passed_to_oci_backend(self):
        """Storage and pool parameters should be passed to OCI backend."""
        spec = {
            'name': 'test-params',
            'type': 'oci',
            'vmid': 207,
            'oci': {
                'image': 'nginx',
                'tag': 'alpine',
            },
        }
        
        with patch.object(self.orchestrator.oci_backend, 'pull_image') as mock_pull, \
             patch.object(self.orchestrator.oci_backend, 'create_container') as mock_create:
            
            mock_pull.return_value = 'local:vztmpl/nginx-alpine.tar'
            mock_create.return_value = 207
            
            self.orchestrator.create_container(spec, storage='tank', pool='web-apps')
            
            # Should pass storage and pool parameters
            mock_create.assert_called_once_with(
                spec=spec,
                template='local:vztmpl/nginx-alpine.tar',
                storage='tank',
                pool='web-apps'
            )


if __name__ == '__main__':
    unittest.main()
