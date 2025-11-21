"""Tests for OCI CLI commands."""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from typer.testing import CliRunner
from tengil.cli import app

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

    def test_remove_command_help(self):
        """Test remove command shows help."""
        result = runner.invoke(app, ["oci", "remove", "--help"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Delete a cached OCI template", result.stdout)
        self.assertIn("--force", result.stdout)

    def test_prune_command_help(self):
        """Test prune command shows help."""
        result = runner.invoke(app, ["oci", "prune", "--help"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Remove all cached OCI templates", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--force", result.stdout)


if __name__ == '__main__':
    unittest.main()
