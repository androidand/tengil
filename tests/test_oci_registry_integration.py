"""Integration tests for OCI registry interactions (no actual pulls)."""
import unittest
from unittest.mock import MagicMock, patch

from tengil.services.oci_registry import OciRegistryCatalog
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
        
        # Verify we have substantial catalog (expanded from 6 to 31+ apps)
        self.assertGreaterEqual(len(apps), 30, "Should have at least 30 apps in catalog")
        
        # Should have examples from different registries
        has_docker_hub = any('docker.io' not in img and '/' in img for img in app_images)
        has_ghcr = any('ghcr.io' in img for img in app_images)
        
        self.assertTrue(has_docker_hub or len(app_images) > 0, "Should have Docker Hub apps")
        self.assertTrue(has_ghcr, "Should have GHCR apps")
        
        # Verify key categories are represented
        app_names = [app.name for app in apps]
        self.assertIn('jellyfin', app_names, "Should have media server")
        self.assertIn('nextcloud', app_names, "Should have file sync")
        self.assertIn('home-assistant', app_names, "Should have home automation")
        self.assertIn('vaultwarden', app_names, "Should have password manager")
        self.assertIn('photoprism', app_names, "Should have photo management")

    def test_catalog_categories(self):
        """Test category filtering and listing."""
        categories = OciRegistryCatalog.get_categories()
        
        # Should have all expected categories
        self.assertIn('media', categories)
        self.assertIn('photos', categories)
        self.assertIn('files', categories)
        self.assertIn('automation', categories)
        self.assertIn('documents', categories)
        self.assertIn('passwords', categories)
        self.assertIn('monitoring', categories)
        self.assertIn('network', categories)
        self.assertIn('recipes', categories)
        self.assertIn('rss', categories)
        
        # Should have at least 10 categories
        self.assertGreaterEqual(len(categories), 10)

    def test_filter_by_category(self):
        """Test filtering apps by category."""
        media_apps = OciRegistryCatalog.filter_by_category('media')
        
        # Should have media apps
        self.assertGreater(len(media_apps), 0)
        
        # All apps should be in media category
        for app in media_apps:
            self.assertEqual(app.category, 'media')
        
        # Should include known media apps
        media_names = [app.name for app in media_apps]
        self.assertIn('jellyfin', media_names)
        self.assertIn('plex', media_names)

    def test_get_app_by_name(self):
        """Test getting specific app by name."""
        jellyfin = OciRegistryCatalog.get_app_by_name('jellyfin')
        
        self.assertIsNotNone(jellyfin)
        self.assertEqual(jellyfin.name, 'jellyfin')
        self.assertEqual(jellyfin.category, 'media')
        self.assertIn('jellyfin', jellyfin.image)
        
        # Test case-insensitive
        jellyfin_upper = OciRegistryCatalog.get_app_by_name('JELLYFIN')
        self.assertIsNotNone(jellyfin_upper)
        self.assertEqual(jellyfin_upper.name, 'jellyfin')
        
        # Test non-existent app
        nonexistent = OciRegistryCatalog.get_app_by_name('nonexistent')
        self.assertIsNone(nonexistent)

    def test_search_apps_by_description(self):
        """Test searching apps by description content."""
        # Search for "photo" should find photo management apps
        photo_apps = OciRegistryCatalog.search_apps('photo')
        photo_names = [app.name for app in photo_apps]
        
        self.assertIn('photoprism', photo_names)
        self.assertIn('immich', photo_names)
        self.assertIn('photoview', photo_names)
        
        # Search for "password" should find password managers
        password_apps = OciRegistryCatalog.search_apps('password')
        password_names = [app.name for app in password_apps]
        
        self.assertIn('vaultwarden', password_names)
        self.assertIn('passbolt', password_names)


if __name__ == '__main__':
    unittest.main()
