"""Test rpool safety checks."""
import pytest
import tempfile
from pathlib import Path
import yaml

from tengil.config.loader import ConfigLoader


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    import shutil
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)


def test_rpool_reserved_paths_warning(temp_dir, caplog):
    """Test warning when using Proxmox-reserved paths on rpool."""
    config_path = temp_dir / "tengil.yml"
    config = {
        'version': 2,
        'pools': {
            'rpool': {
                'type': 'zfs',
                'datasets': {
                    'ROOT/test': {'profile': 'dev'},  # BAD - Proxmox reserved
                }
            }
        }
    }
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    import logging
    caplog.set_level(logging.WARNING)
    
    loader = ConfigLoader(config_path)
    config = loader.load()
    
    # Should have warning about ROOT
    assert any('Proxmox-reserved' in record.message for record in caplog.records)
    assert any('ROOT' in record.message for record in caplog.records)


def test_rpool_data_reserved_warning(temp_dir, caplog):
    """Test warning for rpool/data."""
    config_path = temp_dir / "tengil.yml"
    config = {
        'version': 2,
        'pools': {
            'rpool': {
                'type': 'zfs',
                'datasets': {
                    'data/something': {'profile': 'dev'},  # BAD
                }
            }
        }
    }
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    import logging
    caplog.set_level(logging.WARNING)
    
    loader = ConfigLoader(config_path)
    config = loader.load()
    
    assert any('Proxmox-reserved' in record.message for record in caplog.records)


def test_rpool_tengil_namespace_safe(temp_dir, caplog):
    """Test that rpool/tengil/* is considered safe."""
    config_path = temp_dir / "tengil.yml"
    config = {
        'version': 2,
        'pools': {
            'rpool': {
                'type': 'zfs',
                'datasets': {
                    'tengil/appdata': {'profile': 'dev'},  # GOOD
                    'tengil/databases': {'profile': 'dev'},  # GOOD
                }
            }
        }
    }
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    import logging
    caplog.set_level(logging.WARNING)
    
    loader = ConfigLoader(config_path)
    config = loader.load()
    
    # Should not have Proxmox-reserved warnings
    assert not any('Proxmox-reserved' in record.message for record in caplog.records)


def test_rpool_suggests_tengil_namespace(temp_dir, caplog):
    """Test suggestion to use tengil namespace (only with multiple datasets)."""
    config_path = temp_dir / "tengil.yml"
    config = {
        'version': 2,
        'pools': {
            'rpool': {
                'type': 'zfs',
                'datasets': {
                    'appdata': {'profile': 'dev'},
                    'databases': {'profile': 'dev'},
                    'cache': {'profile': 'dev'},  # Multiple datasets triggers suggestion
                }
            }
        }
    }
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    import logging
    caplog.set_level(logging.WARNING)
    
    loader = ConfigLoader(config_path)
    config = loader.load()
    
    # Should suggest using tengil namespace
    assert any('Consider' in record.message for record in caplog.records)
    assert any('optional' in record.message.lower() for record in caplog.records)


def test_tank_no_warnings(temp_dir, caplog):
    """Test that non-rpool pools don't get rpool warnings."""
    config_path = temp_dir / "tengil.yml"
    config = {
        'version': 2,
        'pools': {
            'tank': {
                'type': 'zfs',
                'datasets': {
                    'data': {'profile': 'media'},  # Fine on tank
                    'ROOT': {'profile': 'media'},  # Also fine on tank (weird but allowed)
                }
            }
        }
    }
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    import logging
    caplog.set_level(logging.WARNING)
    
    loader = ConfigLoader(config_path)
    config = loader.load()
    
    # Should not have warnings - these checks only apply to rpool
    assert not any('Proxmox-reserved' in record.message for record in caplog.records)
