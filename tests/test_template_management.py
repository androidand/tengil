"""Tests for Phase 2 Task 5: Template download automation."""
import pytest


class TestTemplateDiscovery:
    """Test template listing and availability checking."""

    def test_list_available_templates(self, mock_pm):
        """Test getting list of available templates."""
        templates = mock_pm.containers.list_available_templates()

        assert isinstance(templates, list)
        assert len(templates) > 0
        assert 'debian-12-standard' in templates

    def test_template_exists_locally_common(self, mock_pm):
        """Test checking if common template exists locally."""
        # Common templates should exist in mock
        assert mock_pm.containers.template_exists_locally('debian-12-standard')

    def test_template_exists_locally_missing(self, mock_pm):
        """Test checking if missing template exists locally."""
        # Random template should not exist
        assert not mock_pm.containers.template_exists_locally('fake-template-xyz')


class TestTemplateDownload:
    """Test template download functionality."""

    def test_download_template_success(self, mock_pm):
        """Test downloading a template."""
        success = mock_pm.containers.download_template('ubuntu-22.04-standard')

        assert success is True

    def test_ensure_template_available_already_exists(self, mock_pm):
        """Test ensure_template when template already exists."""
        result = mock_pm.containers.ensure_template_available('debian-12-standard')

        assert result is True

    def test_ensure_template_available_downloads(self, mock_pm):
        """Test ensure_template downloads missing template."""
        # This template doesn't exist locally in mock
        result = mock_pm.containers.ensure_template_available('ubuntu-22.04-standard')

        # Should succeed - it exists locally in mock
        assert result is True

    def test_ensure_template_download_missing(self, mock_pm):
        """Test ensure_template for non-existent template."""
        # Template that doesn't exist locally - mock will download it
        result = mock_pm.containers.ensure_template_available('debian-12-turnkey-mediaserver')

        # Mock mode always succeeds download
        assert result is True


class TestTemplateIntegration:
    """Test template management integrated with container creation."""

    def test_create_container_uses_existing_template(self, mock_pm, basic_container_spec):
        """Test that container creation uses existing template."""
        spec = {**basic_container_spec, 'name': 'test', 'vmid': 501}
        vmid = mock_pm.create_container(spec)

        assert vmid == 501

    def test_create_container_downloads_missing_template(self, mock_pm):
        """Test that container creation auto-downloads missing template."""
        spec = {
            'name': 'test',
            'vmid': 500,
            'template': 'debian-12-turnkey-mediaserver',  # Not locally available
        }

        vmid = mock_pm.create_container(spec)

        # Should succeed because template gets auto-downloaded in mock
        assert vmid == 500

    def test_create_multiple_containers_different_templates(self, mock_pm):
        """Test creating multiple containers with different templates."""
        specs = [
            {'name': 'debian-ct', 'vmid': 510, 'template': 'debian-12-standard'},
            {'name': 'ubuntu-ct', 'vmid': 511, 'template': 'ubuntu-22.04-standard'},
            {'name': 'turnkey-ct', 'vmid': 512, 'template': 'debian-12-turnkey-mediaserver'},
        ]

        for spec in specs:
            vmid = mock_pm.create_container(spec)
            assert vmid == spec['vmid']

    def test_create_container_full_template_name(self, mock_pm):
        """Test that full template names with extensions work correctly."""
        # User provides full template name including version and extension
        spec = {
            'name': 'test-full',
            'vmid': 520,
            'template': 'debian-12-standard_12.2-1_amd64.tar.zst',
        }

        vmid = mock_pm.create_container(spec)

        # Should work without double extension
        assert vmid == 520
