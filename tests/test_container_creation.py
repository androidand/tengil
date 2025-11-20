"""Tests for Phase 2 Task 4: Container creation."""
import pytest
from types import SimpleNamespace

from tengil.services.proxmox.containers.lifecycle import ContainerLifecycle


def _setup_lifecycle(monkeypatch):
    """Return lifecycle instance with subprocess captured."""
    lifecycle = ContainerLifecycle(mock=False)
    monkeypatch.setattr(lifecycle.templates, "ensure_template_available", lambda template: True)
    monkeypatch.setattr(lifecycle.discovery, "container_exists", lambda vmid: False)

    captured = {}

    def fake_run(cmd, capture_output, text, check):
        captured['cmd'] = cmd
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(
        "tengil.services.proxmox.containers.lifecycle.subprocess.run",
        fake_run
    )

    return lifecycle, captured


class TestContainerCreation:
    """Test creating LXC containers."""

    def test_create_basic_container(self, mock_pm, basic_container_spec):
        """Test creating a basic container with minimal config."""
        spec = {**basic_container_spec, 'vmid': 200}
        vmid = mock_pm.create_container(spec)

        assert vmid == 200
        # In mock mode, returns the specified vmid

    def test_create_container_with_resources(self, mock_pm, container_with_resources):
        """Test creating container with custom resources."""
        spec = {**container_with_resources, 'vmid': 100, 'name': 'jellyfin'}
        vmid = mock_pm.create_container(spec)

        assert vmid == 100

    def test_create_container_with_network(self, mock_pm, container_with_network):
        """Test creating container with custom network config."""
        spec = {**container_with_network, 'vmid': 101, 'name': 'nextcloud'}
        vmid = mock_pm.create_container(spec)

        assert vmid == 101

    def test_create_container_dhcp_network(self, mock_pm, basic_container_spec):
        """Test creating container with DHCP."""
        spec = {
            **basic_container_spec,
            'name': 'test-dhcp',
            'vmid': 102,
            'network': {
                'bridge': 'vmbr0',
                'ip': 'dhcp',
            }
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 102

    def test_create_container_auto_vmid(self, mock_pm, basic_container_spec):
        """Test creating container without specifying VMID."""
        spec = {**basic_container_spec, 'name': 'auto-id-container'}
        vmid = mock_pm.create_container(spec)

        # In mock mode, auto-assigns based on spec
        assert vmid is not None
        assert isinstance(vmid, int)

    def test_create_container_no_template_fails(self, mock_pm):
        """Test that creating container without template fails."""
        spec = {
            'name': 'no-template',
            'vmid': 999,
            # Missing template!
        }

        vmid = mock_pm.create_container(spec)

        # Should fail and return None
        assert vmid is None

    def test_create_container_with_full_spec(self, mock_pm):
        """Test creating container with complete specification."""
        spec = {
            'name': 'full-spec',
            'vmid': 150,
            'template': 'debian-12-standard',
            'resources': {
                'memory': 4096,
                'cores': 4,
                'disk': '32G',
                'swap': 1024,
            },
            'network': {
                'bridge': 'vmbr0',
                'ip': '192.168.1.150/24',
                'gateway': '192.168.1.1',
                'firewall': True,
            }
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 150

    def test_create_container_with_pool_flag(self, monkeypatch):
        """Test that resource pool flag is passed to pct create."""
        lifecycle, captured = _setup_lifecycle(monkeypatch)
        spec = {
            'name': 'pool-test',
            'vmid': 999,
            'template': 'debian-12-standard',
            'resources': {
                'memory': 1024
            },
            'pool': 'production'
        }

        vmid = lifecycle.create_container(spec, storage='local')

        assert vmid == 999
        assert '--pool' in captured['cmd']
        pool_index = captured['cmd'].index('--pool')
        assert captured['cmd'][pool_index + 1] == 'production'

    def test_create_container_unprivileged_by_default(self, monkeypatch):
        """Ensure unprivileged flag is set when privileged not requested."""
        lifecycle, captured = _setup_lifecycle(monkeypatch)
        spec = {
            'name': 'unprivileged-test',
            'vmid': 998,
            'template': 'debian-12-standard',
        }

        lifecycle.create_container(spec, storage='local')

        assert '--unprivileged' in captured['cmd']
        assert '--privileged' not in captured['cmd']

    def test_create_container_privileged_flag(self, monkeypatch):
        """Ensure privileged flag is used when requested."""
        lifecycle, captured = _setup_lifecycle(monkeypatch)
        spec = {
            'name': 'priv-test',
            'vmid': 997,
            'template': 'debian-12-standard',
            'privileged': True,
        }

        lifecycle.create_container(spec, storage='local')

        assert '--unprivileged' in captured['cmd']
        unprivileged_index = captured['cmd'].index('--unprivileged')
        assert captured['cmd'][unprivileged_index + 1] == '0'


class TestContainerLifecycle:
    """Test container lifecycle operations (start/stop/restart)."""

    def test_start_container(self, mock_pm):
        """Test starting a container."""
        success = mock_pm.start_container(100)

        assert success is True

    def test_stop_container(self, mock_pm):
        """Test stopping a container."""
        success = mock_pm.stop_container(100)

        assert success is True

    def test_restart_container(self, mock_pm):
        """Test restarting a container."""
        success = mock_pm.restart_container(100)

        assert success is True

    def test_start_multiple_containers(self, mock_pm):
        """Test starting multiple containers."""
        results = []
        for vmid in [100, 101, 102]:
            results.append(mock_pm.start_container(vmid))

        assert all(results)

    def test_restart_multiple_containers(self, mock_pm):
        """Test restarting multiple containers."""
        results = []
        for vmid in [100, 101, 102]:
            results.append(mock_pm.restart_container(vmid))

        assert all(results)


class TestContainerResourceDefaults:
    """Test default values for container resources."""

    def test_create_container_default_resources(self, mock_pm, basic_container_spec):
        """Test that default resources are used when not specified."""
        spec = {**basic_container_spec, 'name': 'defaults', 'vmid': 300}
        vmid = mock_pm.create_container(spec)

        assert vmid == 300
        # Should use defaults: 512MB RAM, 1 core, 8G disk

    def test_create_container_partial_resources(self, mock_pm, basic_container_spec):
        """Test specifying only some resources."""
        spec = {
            **basic_container_spec,
            'name': 'partial',
            'vmid': 301,
            'resources': {
                'memory': 1024,  # Only specify memory
            }
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 301
        # Should use specified memory, defaults for rest


class TestContainerTemplateHandling:
    """Test template-related functionality."""

    def test_create_with_debian_template(self, mock_pm, basic_container_spec):
        """Test creating container with Debian template."""
        spec = {**basic_container_spec, 'name': 'debian-test', 'vmid': 400}
        vmid = mock_pm.create_container(spec)

        assert vmid == 400

    def test_create_with_ubuntu_template(self, mock_pm):
        """Test creating container with Ubuntu template."""
        spec = {
            'name': 'ubuntu-test',
            'vmid': 401,
            'template': 'ubuntu-22.04-standard',
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 401

    def test_create_with_turnkey_template(self, mock_pm):
        """Test creating container with TurnKey template."""
        spec = {
            'name': 'jellyfin-turnkey',
            'vmid': 402,
            'template': 'debian-12-turnkey-mediaserver',
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 402

    def test_create_with_full_template_name(self, mock_pm):
        """Test creating container with full template filename."""
        spec = {
            'name': 'test',
            'vmid': 403,
            'template': 'debian-12-standard_12.2-1_amd64.tar.zst',  # Full filename
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 403


class TestContainerNetworkOptions:
    """Test various network configuration options."""

    def test_create_container_no_network(self, mock_pm, basic_container_spec):
        """Test creating container without network config."""
        spec = {**basic_container_spec, 'name': 'no-net', 'vmid': 500}
        vmid = mock_pm.create_container(spec)

        assert vmid == 500
        # Should use default bridge and DHCP

    def test_create_container_static_ip(self, mock_pm, basic_container_spec):
        """Test creating container with static IP."""
        spec = {
            **basic_container_spec,
            'name': 'static-ip',
            'vmid': 501,
            'network': {
                'bridge': 'vmbr0',
                'ip': '10.0.0.50/24',
                'gateway': '10.0.0.1',
            }
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 501

    def test_create_container_no_firewall(self, mock_pm, basic_container_spec):
        """Test creating container with firewall disabled."""
        spec = {
            **basic_container_spec,
            'name': 'no-firewall',
            'vmid': 502,
            'network': {
                'firewall': False,
            }
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 502


class TestContainerCreationEdgeCases:
    """Test edge cases in container creation."""

    def test_create_container_already_exists(self, mock_pm, basic_container_spec):
        """Test creating container when VMID already exists."""
        # In mock mode, containers 100 and 101 exist
        spec = {
            **basic_container_spec,
            'name': 'duplicate',
            'vmid': 100,  # Already exists in mock
        }

        vmid = mock_pm.create_container(spec)

        # Should return the existing vmid (idempotent)
        assert vmid == 100

    def test_create_container_minimal_spec(self, mock_pm, basic_container_spec):
        """Test creating container with absolute minimum spec."""
        vmid = mock_pm.create_container(basic_container_spec)

        # Should auto-assign vmid and use defaults
        assert vmid is not None

    def test_create_multiple_containers(self, mock_pm):
        """Test creating multiple containers in sequence."""
        specs = [
            {'name': 'container1', 'vmid': 201, 'template': 'debian-12-standard'},
            {'name': 'container2', 'vmid': 202, 'template': 'debian-12-standard'},
            {'name': 'container3', 'vmid': 203, 'template': 'debian-12-standard'},
        ]

        vmids = []
        for spec in specs:
            vmid = mock_pm.create_container(spec)
            vmids.append(vmid)

        assert vmids == [201, 202, 203]
        assert len(set(vmids)) == 3  # All unique


class TestContainerResourcePool:
    """Test resource pool assignment."""

    def test_create_container_with_pool(self, mock_pm, basic_container_spec):
        """Test creating container with resource pool assignment."""
        spec = {
            **basic_container_spec,
            'name': 'production-app',
            'vmid': 600,
            'pool': 'production'
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 600

    def test_create_container_with_pool_in_resources(self, mock_pm, basic_container_spec):
        """Test creating container with pool in resources dict."""
        spec = {
            **basic_container_spec,
            'name': 'staging-app',
            'vmid': 601,
            'resources': {
                'memory': 2048,
                'cores': 2,
                'pool': 'staging'
            }
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 601

    def test_create_container_pool_priority(self, mock_pm, basic_container_spec):
        """Test that top-level pool takes priority over resources.pool."""
        spec = {
            **basic_container_spec,
            'name': 'test-priority',
            'vmid': 602,
            'pool': 'production',  # Top-level
            'resources': {
                'pool': 'staging'  # Should be overridden
            }
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 602

    def test_create_container_without_pool(self, mock_pm, basic_container_spec):
        """Test creating container without pool (should work fine)."""
        spec = {
            **basic_container_spec,
            'name': 'no-pool',
            'vmid': 603
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 603


class TestContainerPrivileged:
    """Test privileged container creation."""

    def test_create_unprivileged_container_default(self, mock_pm, basic_container_spec):
        """Test that containers are unprivileged by default."""
        spec = {
            **basic_container_spec,
            'name': 'unprivileged-default',
            'vmid': 700
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 700

    def test_create_privileged_container(self, mock_pm, basic_container_spec):
        """Test creating privileged container."""
        spec = {
            **basic_container_spec,
            'name': 'privileged-docker',
            'vmid': 701,
            'privileged': True
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 701

    def test_create_explicitly_unprivileged_container(self, mock_pm, basic_container_spec):
        """Test creating explicitly unprivileged container."""
        spec = {
            **basic_container_spec,
            'name': 'explicitly-unprivileged',
            'vmid': 702,
            'privileged': False
        }

        vmid = mock_pm.create_container(spec)

        assert vmid == 702

    def test_privileged_flag_in_pct_command(self, monkeypatch):
        """Test that privileged flag is correctly passed to pct create."""
        lifecycle, captured = _setup_lifecycle(monkeypatch)

        # Test privileged container
        spec = {
            'name': 'privileged-test',
            'vmid': 999,
            'template': 'debian-12-standard',
            'privileged': True
        }

        vmid = lifecycle.create_container(spec, storage='local')

        assert vmid == 999
        assert '--unprivileged' in captured['cmd']
        unprivileged_index = captured['cmd'].index('--unprivileged')
        assert captured['cmd'][unprivileged_index + 1] == '0'

    def test_unprivileged_flag_in_pct_command(self, monkeypatch):
        """Test that unprivileged flag is correctly passed to pct create."""
        lifecycle, captured = _setup_lifecycle(monkeypatch)

        # Test unprivileged container (default)
        spec = {
            'name': 'unprivileged-test',
            'vmid': 998,
            'template': 'debian-12-standard'
            # privileged not specified, should default to False
        }

        vmid = lifecycle.create_container(spec, storage='local')

        assert vmid == 998
        assert '--unprivileged' in captured['cmd']
        unpriv_index = captured['cmd'].index('--unprivileged')
        assert captured['cmd'][unpriv_index + 1] == '1'  # 1 means unprivileged

    def test_description_and_tags_flags(self, monkeypatch):
        """Ensure description and tags are passed to pct create."""
        lifecycle, captured = _setup_lifecycle(monkeypatch)
        spec = {
            'name': 'metadata-test',
            'vmid': 996,
            'template': 'debian-12-standard',
            'description': 'Media server',
            'tags': ['media', 'auto']
        }

        lifecycle.create_container(spec, storage='local')

        assert '--description' in captured['cmd']
        assert captured['cmd'][captured['cmd'].index('--description') + 1] == 'Media server'
        assert '--tags' in captured['cmd']
        tags_value = captured['cmd'][captured['cmd'].index('--tags') + 1]
        assert tags_value == 'media,auto'

    def test_startup_order_and_delay_flags(self, monkeypatch):
        """Ensure startup order/delay are converted to pct flags."""
        lifecycle, captured = _setup_lifecycle(monkeypatch)
        spec = {
            'name': 'startup-test',
            'vmid': 995,
            'template': 'debian-12-standard',
            'startup_order': 1,
            'startup_delay': 30,
        }

        lifecycle.create_container(spec, storage='local')

        assert '--startup' in captured['cmd']
        startup_value = captured['cmd'][captured['cmd'].index('--startup') + 1]
        assert startup_value == 'order=1,up=30'

    def test_custom_startup_string_passed_through(self, monkeypatch):
        """Ensure explicit startup string is used as-is."""
        lifecycle, captured = _setup_lifecycle(monkeypatch)
        spec = {
            'name': 'startup-custom',
            'vmid': 994,
            'template': 'debian-12-standard',
            'startup': 'order=5,down=60',
        }

        lifecycle.create_container(spec, storage='local')

        assert '--startup' in captured['cmd']
        startup_value = captured['cmd'][captured['cmd'].index('--startup') + 1]
        assert startup_value == 'order=5,down=60'
