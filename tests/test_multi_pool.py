"""Test multi-pool configuration support."""
import pytest
import tempfile
from pathlib import Path
import yaml

from tengil.config.loader import ConfigLoader
from tengil.models.config import ConfigValidationError


def test_v2_multi_pool():
    """Test v2 multi-pool configuration."""
    v2_config = {
        'version': 2,
        'pools': {
            'rpool': {
                'type': 'zfs',
                'datasets': {
                    'appdata': {
                        'profile': 'dev'
                    }
                }
            },
            'tank': {
                'type': 'zfs',
                'datasets': {
                    'media': {
                        'profile': 'media'
                    }
                }
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(v2_config, f)
        config_path = f.name
    
    try:
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        assert config['version'] == 2
        assert len(config['pools']) == 2
        assert 'rpool' in config['pools']
        assert 'tank' in config['pools']
    finally:
        Path(config_path).unlink()


def test_invalid_pool_name():
    """Test that invalid pool names are rejected."""
    invalid_configs = [
        {'version': 2, 'pools': {'mirror': {'type': 'zfs', 'datasets': {}}}},  # Reserved word
        {'version': 2, 'pools': {'-pool': {'type': 'zfs', 'datasets': {}}}},  # Starts with hyphen
        {'version': 2, 'pools': {'my pool': {'type': 'zfs', 'datasets': {}}}},  # Contains space
    ]
    
    for invalid_config in invalid_configs:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(invalid_config, f)
            config_path = f.name
        
        try:
            loader = ConfigLoader(config_path)
            with pytest.raises(ConfigValidationError):
                loader.load()
        finally:
            Path(config_path).unlink()


def test_cross_pool_hardlink_warning(caplog):
    """Test that cross-pool *arr configurations generate warnings."""
    config = {
        'version': 2,
        'pools': {
            'nvme': {
                'type': 'zfs',
                'datasets': {
                    'downloads': {
                        'profile': 'media',
                        'containers': [
                            {'name': 'sonarr', 'mount': '/downloads'}
                        ]
                    }
                }
            },
            'tank': {
                'type': 'zfs',
                'datasets': {
                    'tv': {
                        'profile': 'media',
                        'containers': [
                            {'name': 'sonarr', 'mount': '/tv'}
                        ]
                    }
                }
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(config, f)
        config_path = f.name
    
    try:
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        # Should have generated a warning about cross-pool mounts
        assert any('sonarr' in record.message and 'multiple pools' in record.message 
                  for record in caplog.records)
    finally:
        Path(config_path).unlink()


def test_profile_application_v2():
    """Test that profiles are applied correctly in v2 config."""
    config = {
        'version': 2,
        'pools': {
            'tank': {
                'type': 'zfs',
                'datasets': {
                    'media': {
                        'profile': 'media'
                    }
                }
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(config, f)
        config_path = f.name
    
    try:
        loader = ConfigLoader(config_path)
        loaded_config = loader.load()
        
        # Check that media profile was applied
        dataset = loaded_config['pools']['tank']['datasets']['media']
        assert 'zfs' in dataset
        assert dataset['zfs']['recordsize'] == '1M'
        assert dataset['zfs']['compression'] == 'off'
    finally:
        Path(config_path).unlink()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
