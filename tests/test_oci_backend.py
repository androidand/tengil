"""Unit tests for OCIBackend."""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tengil.services.proxmox.backends.oci import OCIBackend


class TestOCIBackend(unittest.TestCase):
    """Test OCI backend functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.backend = OCIBackend(mock=True)

    def test_pull_image_default_registry(self):
        """Test pulling image from default registry (Docker Hub)."""
        result = self.backend.pull_image('jellyfin/jellyfin', 'latest')
        self.assertEqual(result, 'local:vztmpl/jellyfin-latest.tar')

    def test_pull_image_custom_registry(self):
        """Test pulling image from custom registry."""
        result = self.backend.pull_image(
            'linuxserver/jellyfin',
            'latest',
            'ghcr.io'
        )
        self.assertEqual(result, 'local:vztmpl/jellyfin-latest.tar')

    def test_create_container_minimal(self):
        """Test creating container with minimal spec."""
        spec = {
            'oci': {
                'image': 'alpine',
                'tag': 'latest'
            },
            'hostname': 'test-alpine',
            'cores': 2,
            'memory': 512,
            'disk': 8
        }
        
        vmid = self.backend.create_container(spec)
        self.assertEqual(vmid, 200)

    def test_create_container_with_gpu(self):
        """Test creating container with GPU passthrough."""
        spec = {
            'oci': {
                'image': 'jellyfin/jellyfin',
                'tag': 'latest'
            },
            'hostname': 'jellyfin',
            'cores': 4,
            'memory': 4096,
            'disk': 16,
            'gpu': {
                'passthrough': True
            }
        }
        
        vmid = self.backend.create_container(spec)
        self.assertEqual(vmid, 200)

    def test_create_container_with_mounts(self):
        """Test creating container with ZFS mounts."""
        spec = {
            'oci': {
                'image': 'jellyfin/jellyfin',
                'tag': 'latest'
            },
            'hostname': 'jellyfin',
            'cores': 4,
            'memory': 4096,
            'disk': 16,
            'mounts': [
                {
                    'source': '/tank/media',
                    'target': '/media',
                    'readonly': True
                }
            ]
        }
        
        vmid = self.backend.create_container(spec)
        self.assertEqual(vmid, 200)

    def test_create_container_with_env(self):
        """Test creating container with env vars passed at create time."""
        spec = {
            'oci': {
                'image': 'alpine',
                'tag': 'latest'
            },
            'hostname': 'env-test',
            'env': {
                'KEY': 'VALUE',
                'FOO': 'BAR'
            }
        }
        
        # Test in mock mode - check that command is generated
        import io
        import sys
        captured_output = io.StringIO()
        sys.stdout = captured_output
        try:
            vmid = self.backend.create_container(spec)
            self.assertEqual(vmid, 200)
            output = captured_output.getvalue()
            # Ensure env flags are present in the mock command
            self.assertIn('--env', output)
            self.assertIn('KEY=VALUE', output)
            self.assertIn('FOO=BAR', output)
        finally:
            sys.stdout = sys.__stdout__

    def test_create_container_no_image(self):
        """Test error handling when no image specified."""
        spec = {
            'hostname': 'test'
        }
        
        vmid = self.backend.create_container(spec)
        self.assertIsNone(vmid)

    def test_start_container(self):
        """Test starting a container."""
        result = self.backend.start_container(200)
        self.assertTrue(result)

    def test_stop_container(self):
        """Test stopping a container."""
        result = self.backend.stop_container(200)
        self.assertTrue(result)

    def test_destroy_container(self):
        """Test destroying a container."""
        result = self.backend.destroy_container(200)
        self.assertTrue(result)

    def test_configure_gpu(self):
        """Test GPU configuration."""
        result = self.backend.configure_gpu(200)
        self.assertTrue(result)

    @patch('subprocess.run')
    def test_real_pull_image(self, mock_run):
        """Test actual skopeo command execution."""
        backend = OCIBackend(mock=False)
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        
        _ = backend.pull_image('alpine', 'latest')
        
        # Verify skopeo was called correctly
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], 'skopeo')
        self.assertEqual(args[1], 'copy')
        self.assertIn('docker://docker.io/alpine:latest', args)
        self.assertIn('oci-archive:', args[3])

    @patch('subprocess.run')
    def test_real_create_container(self, mock_run):
        """Test actual pct create command execution."""
        backend = OCIBackend(mock=False)
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        
        # Mock template existence
        with patch.object(Path, 'exists', return_value=True):
            spec = {
                'oci': {
                    'image': 'alpine',
                    'tag': 'latest'
                },
                'hostname': 'test-alpine',
                'cores': 2,
                'memory': 512,
                'disk': 8
            }
            
            _ = backend.create_container(spec, storage='tank')
            
            # Verify pct create was called
            args = mock_run.call_args[0][0]
            self.assertEqual(args[0], 'pct')
            self.assertEqual(args[1], 'create')
            self.assertIn('--hostname', args)
            self.assertIn('test-alpine', args)
            self.assertIn('--rootfs', args)
            self.assertIn('tank:8', args)


if __name__ == '__main__':
    unittest.main()
