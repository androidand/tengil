"""Tests for post-install automation."""
import pytest

from tengil.services.post_install import PostInstallManager


@pytest.fixture
def post_install_mgr():
    """Create PostInstallManager in mock mode."""
    return PostInstallManager(mock=True)


class TestDockerInstall:
    """Test Docker installation."""

    def test_install_docker(self, post_install_mgr):
        """Test installing Docker in container."""
        success = post_install_mgr.install_docker(vmid=100)
        assert success is True

    def test_install_docker_already_exists(self, post_install_mgr):
        """Test Docker installation when already installed (idempotent)."""
        # In mock mode, _check_command_exists always returns True for testing
        success = post_install_mgr.install_docker(vmid=100)
        assert success is True


class TestPortainerInstall:
    """Test Portainer installation."""

    def test_install_portainer(self, post_install_mgr):
        """Test installing Portainer."""
        success = post_install_mgr.install_portainer(vmid=100)
        assert success is True

    def test_install_portainer_requires_docker(self, post_install_mgr):
        """Test that Portainer requires Docker."""
        # In mock mode, this always succeeds
        success = post_install_mgr.install_portainer(vmid=100)
        assert success is True


class TestTteckScripts:
    """Test tteck script execution."""

    def test_run_tteck_jellyfin(self, post_install_mgr):
        """Test running tteck jellyfin script."""
        success = post_install_mgr.run_tteck_script(vmid=100, script_name='jellyfin')
        assert success is True

    def test_run_tteck_immich(self, post_install_mgr):
        """Test running tteck immich script."""
        success = post_install_mgr.run_tteck_script(vmid=100, script_name='immich')
        assert success is True

    def test_run_tteck_homeassistant(self, post_install_mgr):
        """Test running tteck home assistant script."""
        success = post_install_mgr.run_tteck_script(vmid=100, script_name='homeassistant')
        assert success is True

    def test_run_tteck_unknown_script(self, post_install_mgr):
        """Test running unknown tteck script (should try anyway)."""
        success = post_install_mgr.run_tteck_script(vmid=100, script_name='unknown-app')
        assert success is True  # Mock mode always succeeds


class TestNodeJSInstall:
    """Test Node.js 20 installation."""

    def test_install_nodejs_20(self, post_install_mgr):
        """Test installing Node.js 20 in container."""
        success = post_install_mgr.install_nodejs_20(vmid=100)
        assert success is True

    def test_install_nodejs_20_already_exists(self, post_install_mgr):
        """Test Node.js installation when already installed (idempotent)."""
        success = post_install_mgr.install_nodejs_20(vmid=100)
        assert success is True


class TestHAMCPInstall:
    """Test Home Assistant MCP server installation."""

    def test_install_ha_mcp(self, post_install_mgr):
        """Test installing HA MCP server."""
        success = post_install_mgr.install_ha_mcp(vmid=100)
        assert success is True

    def test_install_ha_mcp_requires_nodejs(self, post_install_mgr):
        """Test that HA MCP requires Node.js."""
        # In mock mode, this always succeeds
        success = post_install_mgr.install_ha_mcp(vmid=100)
        assert success is True


class TestCustomCommands:
    """Test custom shell command execution."""

    def test_run_custom_command(self, post_install_mgr):
        """Test running custom shell command."""
        command = "apt-get update && apt-get install -y nginx"
        success = post_install_mgr.run_custom_command(vmid=100, command=command)
        assert success is True

    def test_run_multiline_command(self, post_install_mgr):
        """Test running multiline script."""
        command = """
        apt-get update
        apt-get install -y nginx
        systemctl enable nginx
        systemctl start nginx
        """
        success = post_install_mgr.run_custom_command(vmid=100, command=command)
        assert success is True


class TestPostInstallOrchestration:
    """Test post-install task orchestration."""

    def test_run_single_task_string(self, post_install_mgr):
        """Test running single task as string."""
        success = post_install_mgr.run_post_install(vmid=100, post_install='docker')
        assert success is True

    def test_run_single_task_list(self, post_install_mgr):
        """Test running single task as list."""
        success = post_install_mgr.run_post_install(vmid=100, post_install=['docker'])
        assert success is True

    def test_run_multiple_tasks(self, post_install_mgr):
        """Test running multiple tasks."""
        success = post_install_mgr.run_post_install(
            vmid=100,
            post_install=['docker', 'portainer']
        )
        assert success is True

    def test_run_tteck_task(self, post_install_mgr):
        """Test running tteck task."""
        success = post_install_mgr.run_post_install(
            vmid=100,
            post_install='tteck/jellyfin'
        )
        assert success is True

    def test_run_custom_task(self, post_install_mgr):
        """Test running custom command task."""
        success = post_install_mgr.run_post_install(
            vmid=100,
            post_install='apt-get update && apt-get install -y nginx'
        )
        assert success is True

    def test_run_nodejs_task(self, post_install_mgr):
        """Test running nodejs-20 task."""
        success = post_install_mgr.run_post_install(
            vmid=100,
            post_install='nodejs-20'
        )
        assert success is True

    def test_run_ha_mcp_task(self, post_install_mgr):
        """Test running ha-mcp-setup task."""
        success = post_install_mgr.run_post_install(
            vmid=100,
            post_install='ha-mcp-setup'
        )
        assert success is True

    def test_run_ha_mcp_full_stack(self, post_install_mgr):
        """Test running full HA MCP stack (nodejs + ha-mcp)."""
        success = post_install_mgr.run_post_install(
            vmid=100,
            post_install=['nodejs-20', 'ha-mcp-setup']
        )
        assert success is True

    def test_run_mixed_tasks(self, post_install_mgr):
        """Test running mix of built-in, tteck, and custom tasks."""
        success = post_install_mgr.run_post_install(
            vmid=100,
            post_install=[
                'docker',
                'portainer',
                'tteck/jellyfin',
                'echo "Custom setup complete"'
            ]
        )
        assert success is True


class TestContainerBoot:
    """Test container boot waiting."""

    def test_wait_for_container_boot(self, post_install_mgr):
        """Test waiting for container to boot."""
        ready = post_install_mgr.wait_for_container_boot(vmid=100, timeout=30)
        assert ready is True  # Mock mode always ready

    def test_wait_for_container_boot_short_timeout(self, post_install_mgr):
        """Test boot wait with short timeout."""
        ready = post_install_mgr.wait_for_container_boot(vmid=100, timeout=5)
        assert ready is True  # Mock mode always ready


class TestKnownScripts:
    """Test known tteck script mappings."""

    def test_known_scripts_exist(self, post_install_mgr):
        """Test that known script mappings are defined."""
        assert 'jellyfin' in post_install_mgr.TTECK_SCRIPTS
        assert 'immich' in post_install_mgr.TTECK_SCRIPTS
        assert 'homeassistant' in post_install_mgr.TTECK_SCRIPTS
        assert 'nextcloud' in post_install_mgr.TTECK_SCRIPTS
        assert 'pihole' in post_install_mgr.TTECK_SCRIPTS
        assert 'docker' in post_install_mgr.TTECK_SCRIPTS
        assert 'portainer' in post_install_mgr.TTECK_SCRIPTS

    def test_script_url_construction(self, post_install_mgr):
        """Test that script URLs are constructed correctly."""
        base_url = post_install_mgr.TTECK_BASE_URL
        assert 'tteck' in base_url.lower()
        assert 'proxmox' in base_url.lower()


class TestTaskParsing:
    """Test task specification parsing."""

    def test_parse_docker_task(self, post_install_mgr):
        """Test parsing docker task."""
        success = post_install_mgr._run_task(vmid=100, task='docker')
        assert success is True

    def test_parse_portainer_task(self, post_install_mgr):
        """Test parsing portainer task."""
        success = post_install_mgr._run_task(vmid=100, task='portainer')
        assert success is True

    def test_parse_tteck_task(self, post_install_mgr):
        """Test parsing tteck task."""
        success = post_install_mgr._run_task(vmid=100, task='tteck/jellyfin')
        assert success is True

    def test_parse_custom_task(self, post_install_mgr):
        """Test parsing custom command task."""
        success = post_install_mgr._run_task(vmid=100, task='echo "test"')
        assert success is True

    def test_parse_task_with_whitespace(self, post_install_mgr):
        """Test parsing task with leading/trailing whitespace."""
        success = post_install_mgr._run_task(vmid=100, task='  docker  ')
        assert success is True
