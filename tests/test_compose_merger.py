"""
Tests for Docker Compose opinion merger.
"""

import pytest

from tengil.services.docker_compose.analyzer import ComposeRequirements, VolumeMount
from tengil.services.docker_compose.merger import OpinionMerger


@pytest.fixture
def merger():
    """Create merger instance."""
    return OpinionMerger()


@pytest.fixture
def simple_requirements():
    """Create simple compose requirements."""
    requirements = ComposeRequirements()
    requirements.services = ['app']
    requirements.add_volume('/data', '/app/data', 'app')
    requirements.add_volume('/config', '/app/config', 'app', readonly=True)
    requirements.add_secret('SECRET_KEY')
    requirements.add_port('8080:8080')
    return requirements


@pytest.fixture
def romm_requirements():
    """Create romM-like requirements."""
    requirements = ComposeRequirements()
    requirements.services = ['romm', 'romm-db']
    requirements.add_volume('/path/to/library', '/romm/library', 'romm')
    requirements.add_volume('/path/to/assets', '/romm/assets', 'romm')
    requirements.add_volume('/path/to/config', '/romm/config', 'romm')
    requirements.add_secret('DB_PASSWD')
    requirements.add_secret('ROMM_AUTH_SECRET_KEY')
    requirements.add_secret('MARIADB_ROOT_PASSWORD')
    requirements.add_port('80:8080')
    return requirements


@pytest.fixture
def simple_package():
    """Create simple package with storage hints."""
    return {
        'storage_hints': {
            '/data': {
                'profile': 'media',
                'size_estimate': '100GB',
                'why': 'Large files'
            },
            '/config': {
                'profile': 'dev',
                'size_estimate': '1GB',
                'why': 'Config files'
            }
        },
        'share_recommendations': {
            '/data': {
                'smb': True,
                'smb_name': 'Data',
                'read_only': False
            }
        },
        'container': {
            'memory': 2048,
            'cores': 2
        }
    }


@pytest.fixture
def romm_package():
    """Create romM package with storage hints."""
    return {
        'storage_hints': {
            '/path/to/library': {
                'profile': 'media',
                'size_estimate': '500GB',
                'why': 'ROM files',
                'mount_as': '/roms'
            },
            '/path/to/assets': {
                'profile': 'media',
                'size_estimate': '50GB',
                'why': 'Save states',
                'mount_as': '/assets'
            },
            '/path/to/config': {
                'profile': 'dev',
                'size_estimate': '1GB',
                'why': 'Config files',
                'mount_as': '/config'
            }
        },
        'share_recommendations': {
            '/path/to/library': {
                'smb': True,
                'smb_name': 'ROMs',
                'read_only': False
            }
        },
        'container': {
            'memory': 2048,
            'cores': 2,
            'template': 'debian-12-standard'
        }
    }


def test_basic_merge(merger, simple_requirements, simple_package):
    """Test basic merge of requirements and hints."""
    config = merger.merge(simple_requirements, simple_package)
    
    # Check structure
    assert 'version' in config
    assert 'pools' in config
    assert 'tank' in config['pools']
    assert 'datasets' in config['pools']['tank']
    
    datasets = config['pools']['tank']['datasets']
    
    # Check datasets created
    assert 'data' in datasets
    assert 'config' in datasets
    
    # Check data dataset
    data = datasets['data']
    assert data['profile'] == 'media'
    assert data['_why'] == 'Large files'
    assert data['_size_estimate'] == '100GB'
    
    # Check consumers
    assert len(data['consumers']) == 2  # container + smb
    
    container_consumer = next(c for c in data['consumers'] if c['type'] == 'container')
    assert container_consumer['name'] == 'app'
    assert container_consumer['access'] == 'write'
    assert container_consumer['mount'] == '/data'
    
    smb_consumer = next(c for c in data['consumers'] if c['type'] == 'smb')
    assert smb_consumer['name'] == 'Data'
    assert smb_consumer['access'] == 'write'


def test_readonly_volumes(merger, simple_requirements, simple_package):
    """Test that readonly volumes get read access."""
    config = merger.merge(simple_requirements, simple_package)
    
    datasets = config['pools']['tank']['datasets']
    config_dataset = datasets['config']
    
    container_consumer = next(c for c in config_dataset['consumers'] if c['type'] == 'container')
    assert container_consumer['access'] == 'read'


def test_romm_package_merge(merger, romm_requirements, romm_package):
    """Test merging romM compose with storage hints."""
    config = merger.merge(romm_requirements, romm_package)
    
    datasets = config['pools']['tank']['datasets']
    
    # Check datasets use compose paths (not mount_as)
    assert 'path-to-library' in datasets
    assert 'path-to-assets' in datasets
    assert 'path-to-config' in datasets
    
    # Check library dataset
    library = datasets['path-to-library']
    assert library['profile'] == 'media'
    assert library['_why'] == 'ROM files'
    
    # Check consumers
    assert len(library['consumers']) == 2  # romm container + SMB
    
    container = next(c for c in library['consumers'] if c['type'] == 'container')
    assert container['name'] == 'romm'
    assert container['mount'] == '/path/to/library'
    
    smb = next(c for c in library['consumers'] if c['type'] == 'smb')
    assert smb['name'] == 'ROMs'


def test_path_to_dataset_name(merger):
    """Test path to dataset name conversion."""
    assert merger._path_to_dataset_name('/roms') == 'roms'
    assert merger._path_to_dataset_name('/romm/assets') == 'romm-assets'
    assert merger._path_to_dataset_name('/path/to/data') == 'path-to-data'


def test_multiple_services_same_volume(merger):
    """Test multiple services mounting same volume."""
    requirements = ComposeRequirements()
    requirements.services = ['app1', 'app2']
    requirements.add_volume('/data', '/app1/data', 'app1')
    requirements.add_volume('/data', '/app2/data', 'app2')
    
    package = {
        'storage_hints': {
            '/data': {
                'profile': 'media'
            }
        }
    }
    
    config = merger.merge(requirements, package)
    datasets = config['pools']['tank']['datasets']
    
    # Should have one dataset with two container consumers
    assert len(datasets) == 1
    assert 'data' in datasets
    
    data = datasets['data']
    container_consumers = [c for c in data['consumers'] if c['type'] == 'container']
    assert len(container_consumers) == 2
    
    assert any(c['name'] == 'app1' for c in container_consumers)
    assert any(c['name'] == 'app2' for c in container_consumers)


def test_no_duplicate_consumers(merger):
    """Test that duplicate consumers are not added."""
    requirements = ComposeRequirements()
    requirements.services = ['app']
    requirements.add_volume('/data', '/app/data', 'app')
    requirements.add_volume('/data', '/app/data', 'app')  # Duplicate
    
    package = {
        'storage_hints': {
            '/data': {
                'profile': 'media'
            }
        }
    }
    
    config = merger.merge(requirements, package)
    datasets = config['pools']['tank']['datasets']
    
    data = datasets['data']
    container_consumers = [c for c in data['consumers'] if c['type'] == 'container']
    assert len(container_consumers) == 1


def test_smb_share_recommendations(merger, simple_requirements):
    """Test SMB share consumer creation."""
    package = {
        'storage_hints': {
            '/data': {
                'profile': 'media'
            }
        },
        'share_recommendations': {
            '/data': {
                'smb': True,
                'smb_name': 'MyShare',
                'read_only': True
            }
        }
    }
    
    config = merger.merge(simple_requirements, package)
    datasets = config['pools']['tank']['datasets']
    
    data = datasets['data']
    smb = next(c for c in data['consumers'] if c['type'] == 'smb')
    assert smb['name'] == 'MyShare'
    assert smb['access'] == 'read'


def test_nfs_share_recommendations(merger, simple_requirements):
    """Test NFS share consumer creation."""
    package = {
        'storage_hints': {
            '/data': {
                'profile': 'media'
            }
        },
        'share_recommendations': {
            '/data': {
                'nfs': True,
                'read_only': False
            }
        }
    }
    
    config = merger.merge(simple_requirements, package)
    datasets = config['pools']['tank']['datasets']
    
    data = datasets['data']
    nfs = next(c for c in data['consumers'] if c['type'] == 'nfs')
    assert nfs['name'] == 'data'
    assert nfs['access'] == 'write'


def test_container_config_included(merger, simple_requirements, simple_package):
    """Test that container config is included in output."""
    config = merger.merge(simple_requirements, simple_package)
    
    assert 'containers' in config
    assert 'app' in config['containers']
    
    container = config['containers']['app']
    assert container['memory'] == 2048
    assert container['cores'] == 2


def test_metadata_included(merger, simple_requirements, simple_package):
    """Test that metadata is included in output."""
    config = merger.merge(simple_requirements, simple_package)
    
    assert '_metadata' in config
    assert config['_metadata']['generated_from'] == 'docker_compose'
    assert 'app' in config['_metadata']['compose_services']


def test_minimal_package(merger, simple_requirements):
    """Test merge with minimal package (no hints)."""
    package = {}
    
    config = merger.merge(simple_requirements, package)
    
    # Should still create datasets
    datasets = config['pools']['tank']['datasets']
    assert 'data' in datasets
    assert 'config' in datasets
    
    # Should have container consumers
    data = datasets['data']
    assert len(data['consumers']) == 1
    assert data['consumers'][0]['type'] == 'container'


def test_merge_with_profile_only(merger, simple_requirements):
    """Test merge with profile hint only."""
    package = {
        'storage_hints': {
            '/data': {
                'profile': 'media'
            }
        }
    }
    
    config = merger.merge(simple_requirements, package)
    datasets = config['pools']['tank']['datasets']
    
    data = datasets['data']
    assert data['profile'] == 'media'
    assert '_why' not in data
    assert '_size_estimate' not in data


def test_volume_without_hint_gets_default(merger):
    """Test that volumes without hints still get created."""
    requirements = ComposeRequirements()
    requirements.services = ['app']
    requirements.add_volume('/unmapped', '/app/unmapped', 'app')
    
    package = {
        'storage_hints': {
            '/other': {
                'profile': 'media'
            }
        }
    }
    
    config = merger.merge(requirements, package)
    datasets = config['pools']['tank']['datasets']
    
    # Should create dataset even without hint
    assert 'unmapped' in datasets
    unmapped = datasets['unmapped']
    
    # Should not have profile (no hint provided)
    assert 'profile' not in unmapped
    
    # Should have consumer
    assert len(unmapped['consumers']) == 1
    assert unmapped['consumers'][0]['name'] == 'app'
