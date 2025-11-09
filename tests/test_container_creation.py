"""Tests for Phase 2 Task 4: Container creation."""
import pytest


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


class TestContainerLifecycle:
    """Test container lifecycle operations (start/stop)."""

    def test_start_container(self, mock_pm):
        """Test starting a container."""
        success = mock_pm.start_container(100)

        assert success is True

    def test_stop_container(self, mock_pm):
        """Test stopping a container."""
        success = mock_pm.stop_container(100)

        assert success is True

    def test_start_multiple_containers(self, mock_pm):
        """Test starting multiple containers."""
        results = []
        for vmid in [100, 101, 102]:
            results.append(mock_pm.start_container(vmid))

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
