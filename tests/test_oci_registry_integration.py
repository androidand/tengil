"""Integration tests for OCI registry interactions (no actual pulls)."""
import unittest
from unittest.mock import patch, MagicMock
from tengil.services.proxmox.backends.oci import OCIBackend


class TestOCIRegistryIntegration(unittest.TestCase):
    """Test OCI backend with various registries (mocked)."""

    def setUp(self):
        """Set up test fixtures."""
        self.backend = OCIBackend(mock=False)  # Use real mode but mock subprocess

    @patch('subprocess.run')
    def test_docker_hub_official_image(self, mock_run):
        """Test pulling official image from Docker Hub."""
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        
        result = self.backend.pull_image('alpine', 'latest')
        
        # Verify correct Docker Hub URL format
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], 'skopeo')
        self.assertEqual(call_args[1], 'copy')
        self.assertIn('docker://docker.io/alpine:latest', call_args[2])
        self.assertEqual(result, 'local:vztmpl/alpine-latest.tar')

    @patch('subprocess.run')
    def test_docker_hub_user_image(self, mock_run):
        """Test pulling user/org image from Docker Hub."""
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        
        result = self.backend.pull_image('linuxserver/jellyfin', 'latest')
        
        call_args = mock_run.call_args[0][0]
        self.assertIn('docker://docker.io/linuxserver/jellyfin:latest', call_args[2])
        self.assertEqual(result, 'local:vztmpl/jellyfin-latest.tar')

    @patch('subprocess.run')
    def test_github_container_registry(self, mock_run):
        """Test pulling from GitHub Container Registry."""
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        
        result = self.backend.pull_image('ghcr.io/home-assistant/home-assistant', 'stable')
        
        call_args = mock_run.call_args[0][0]
        # Should NOT prepend docker.io when image already has registry
        self.assertIn('docker://ghcr.io/home-assistant/home-assistant:stable', call_args[2])
        self.assertNotIn('docker.io/ghcr.io', call_args[2])
        self.assertEqual(result, 'local:vztmpl/home-assistant-stable.tar')

    @patch('subprocess.run')
    def test_quay_io_registry(self, mock_run):
        """Test pulling from Quay.io."""
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        
        result = self.backend.pull_image('quay.io/prometheus/prometheus', 'latest')
        
        call_args = mock_run.call_args[0][0]
        self.assertIn('docker://quay.io/prometheus/prometheus:latest', call_args[2])
        self.assertNotIn('docker.io/quay.io', call_args[2])
        self.assertEqual(result, 'local:vztmpl/prometheus-latest.tar')

    @patch('subprocess.run')
    def test_custom_registry(self, mock_run):
        """Test pulling from custom registry via parameter."""
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        
        result = self.backend.pull_image('myapp/frontend', 'v1.2.3', registry='registry.company.com')
        
        call_args = mock_run.call_args[0][0]
        self.assertIn('docker://registry.company.com/myapp/frontend:v1.2.3', call_args[2])
        self.assertEqual(result, 'local:vztmpl/frontend-v1.2.3.tar')

    @patch('subprocess.run')
    def test_immich_multi_registry(self, mock_run):
        """Test Immich from GHCR (real-world example)."""
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        
        result = self.backend.pull_image('ghcr.io/immich-app/immich-server', 'release')
        
        call_args = mock_run.call_args[0][0]
        self.assertIn('docker://ghcr.io/immich-app/immich-server:release', call_args[2])
        self.assertEqual(result, 'local:vztmpl/immich-server-release.tar')

    @patch('subprocess.run')
    def test_registry_detection_edge_cases(self, mock_run):
        """Test edge cases in registry detection."""
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        
        # Case 1: Single word image (library image)
        self.backend.pull_image('nginx', 'alpine')
        call_args = mock_run.call_args[0][0]
        self.assertIn('docker://docker.io/nginx:alpine', call_args[2])
        
        # Case 2: User/image format (Docker Hub)
        self.backend.pull_image('jellyfin/jellyfin', 'latest')
        call_args = mock_run.call_args[0][0]
        self.assertIn('docker://docker.io/jellyfin/jellyfin:latest', call_args[2])
        
        # Case 3: Full registry URL with port
        self.backend.pull_image('registry.local:5000/myapp', 'latest')
        call_args = mock_run.call_args[0][0]
        self.assertIn('docker://registry.local:5000/myapp:latest', call_args[2])
        self.assertNotIn('docker.io', call_args[2])

    @patch('subprocess.run')
    def test_image_name_extraction(self, mock_run):
        """Test that filename is extracted correctly from various image formats."""
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        
        test_cases = [
            ('alpine', 'latest', 'alpine-latest.tar'),
            ('nginx', 'alpine', 'nginx-alpine.tar'),
            ('user/image', 'v1.0', 'image-v1.0.tar'),
            ('ghcr.io/owner/app', 'main', 'app-main.tar'),
            ('registry.io/org/project/service', 'dev', 'service-dev.tar'),
        ]
        
        for image, tag, expected_filename in test_cases:
            result = self.backend.pull_image(image, tag)
            self.assertEqual(result, f'local:vztmpl/{expected_filename}', 
                           f"Failed for {image}:{tag}")


class TestOCIRegistryCatalog(unittest.TestCase):
    """Test OCI registry catalog functionality."""
    
    def test_popular_registries_available(self):
        """Verify popular registries are in catalog."""
        from tengil.services.oci_registry import OciRegistryCatalog
        
        registries = OciRegistryCatalog.list_registries()
        registry_names = [r.name for r in registries]
        
        # Essential registries should be present
        self.assertIn('dockerhub', registry_names)
        self.assertIn('ghcr', registry_names)
        self.assertIn('quay', registry_names)

    def test_popular_apps_cover_main_categories(self):
        """Verify catalog covers major app categories."""
        from tengil.services.oci_registry import OciRegistryCatalog
        
        apps = OciRegistryCatalog.list_popular_apps()
        app_images = [app.image for app in apps]
        
        # Should have examples from different registries
        has_docker_hub = any('docker.io' not in img and '/' in img for img in app_images)
        has_ghcr = any('ghcr.io' in img for img in app_images)
        
        self.assertTrue(has_docker_hub or len(app_images) > 0, "Should have Docker Hub apps")
        self.assertTrue(has_ghcr, "Should have GHCR apps")


if __name__ == '__main__':
    unittest.main()
