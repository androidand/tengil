"""Tests for OCI CLI commands."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from tengil.cli import app
from tengil.services.proxmox.backends.oci import OCIBackend
from tengil.services.proxmox.containers.discovery import ContainerDiscovery

runner = CliRunner()


class TestOCICommands(unittest.TestCase):
    """Test OCI CLI commands."""

    def test_catalog_list_categories(self):
        """Test catalog --list-categories command."""
        result = runner.invoke(app, ["oci", "catalog", "--list-categories"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Available Categories", result.stdout)
        self.assertIn("media", result.stdout)
        self.assertIn("photos", result.stdout)
        self.assertIn("files", result.stdout)

    def test_catalog_filter_by_category(self):
        """Test catalog --category filter."""
        result = runner.invoke(app, ["oci", "catalog", "--category", "media"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Apps in category: media", result.stdout)
        self.assertIn("jellyfin", result.stdout)
        self.assertIn("plex", result.stdout)

    def test_search_command(self):
        """Test search command."""
        result = runner.invoke(app, ["oci", "search", "photo"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("matching 'photo'", result.stdout)
        self.assertIn("photoprism", result.stdout)
        self.assertIn("immich", result.stdout)

    def test_info_command_existing_app(self):
        """Test info command for existing app."""
        result = runner.invoke(app, ["oci", "info", "jellyfin"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("JELLYFIN", result.stdout)
        self.assertIn("Media server", result.stdout)
        self.assertIn("Image:", result.stdout)
        self.assertIn("Registry:", result.stdout)

    def test_info_command_nonexistent_app(self):
        """Test info command for non-existent app."""
        result = runner.invoke(app, ["oci", "info", "nonexistent"])
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.stdout)

    def test_remove_templates_with_wildcard(self):
        """Remove cached templates matching an image wildcard."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "alpine-latest.tar").write_text("alpine")
            (tmp_path / "alpine-3.19.tar").write_text("alpine")
            (tmp_path / "nginx-latest.tar").write_text("nginx")

            def fake_init(self, node="localhost", mock=False):
                self.node = node
                self.mock = mock
                self.template_dir = tmp_path

            with patch.object(OCIBackend, "__init__", fake_init):
                with patch.object(ContainerDiscovery, "get_all_containers_info", return_value=[]):
                    result = runner.invoke(app, ["oci", "remove", "alpine:*", "--force"])

            self.assertEqual(result.exit_code, 0)
            self.assertFalse((tmp_path / "alpine-latest.tar").exists())
            self.assertFalse((tmp_path / "alpine-3.19.tar").exists())
            self.assertTrue((tmp_path / "nginx-latest.tar").exists())

    def test_remove_blocks_in_use_templates(self):
        """Do not remove templates referenced by existing containers."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            target = tmp_path / "alpine-latest.tar"
            target.write_text("alpine")

            def fake_init(self, node="localhost", mock=False):
                self.node = node
                self.mock = mock
                self.template_dir = tmp_path

            containers = [{"template": "local:vztmpl/alpine-latest.tar"}]
            with patch.object(OCIBackend, "__init__", fake_init):
                with patch.object(ContainerDiscovery, "get_all_containers_info", return_value=containers):
                    result = runner.invoke(app, ["oci", "remove", "alpine:latest", "--force"])

            self.assertNotEqual(result.exit_code, 0)
            self.assertTrue(target.exists())
            self.assertIn("in use", result.stdout)

    def test_prune_dry_run_only_unused(self):
        """Prune reports unused templates and leaves in-use ones when dry-run."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            keep = tmp_path / "keep.tar"
            remove = tmp_path / "remove.tar"
            keep.write_text("keep")
            remove.write_text("remove")

            def fake_init(self, node="localhost", mock=False):
                self.node = node
                self.mock = mock
                self.template_dir = tmp_path

            containers = [{"template": "local:vztmpl/keep.tar"}]
            with patch.object(OCIBackend, "__init__", fake_init):
                with patch.object(ContainerDiscovery, "get_all_containers_info", return_value=containers):
                    result = runner.invoke(app, ["oci", "prune", "--dry-run"])

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(keep.exists())
            self.assertTrue(remove.exists())
            self.assertIn("Dry run", result.stdout)
            self.assertIn("remove.tar", result.stdout)


if __name__ == '__main__':
    unittest.main()
