"""Shared test fixtures for Tengil tests."""
import pytest
import tempfile
from pathlib import Path
from tengil.services.proxmox.manager import ProxmoxManager


@pytest.fixture
def mock_pm():
    """Create ProxmoxManager in mock mode."""
    return ProxmoxManager(mock=True)


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    temp = Path(tempfile.mkdtemp())
    yield temp
    # Cleanup handled by OS tempdir cleanup


# Common test data
@pytest.fixture
def basic_container_spec():
    """Basic container specification."""
    return {
        'name': 'test-container',
        'template': 'debian-12-standard',
    }


@pytest.fixture
def container_with_resources():
    """Container spec with custom resources."""
    return {
        'name': 'test-container',
        'template': 'debian-12-standard',
        'resources': {
            'memory': 2048,
            'cores': 2,
            'disk': '16G',
            'swap': 512,
        }
    }


@pytest.fixture
def container_with_network():
    """Container spec with network config."""
    return {
        'name': 'test-container',
        'template': 'debian-12-standard',
        'network': {
            'bridge': 'vmbr0',
            'ip': '192.168.1.100/24',
            'gateway': '192.168.1.1',
            'firewall': True,
        }
    }
