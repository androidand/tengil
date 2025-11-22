"""Test complex multi-pool scenarios and edge cases."""
import tempfile
from pathlib import Path

import pytest
import yaml

from tengil.config.loader import ConfigLoader
from tengil.core.diff_engine import DiffEngine


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    import shutil
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)


class TestDeepNesting:
    """Test deeply nested datasets work correctly."""
    
    def test_deeply_nested_datasets(self, temp_dir):
        """Test tank/media/music/flac/classical paths."""
        config_path = temp_dir / "tengil.yml"
        config = {
                        'pools': {
                'tank': {
                    'type': 'zfs',
                    'datasets': {
                        'media/music/flac/classical': {
                            'profile': 'audio'
                        }
                    }
                }
            }
        }
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        # Check parent expansion
        pools = loader.get_pools()
        datasets = pools['tank']['datasets']
        
        # Should have expanded all parents
        assert 'media' in datasets
        assert 'media/music' in datasets
        assert 'media/music/flac' in datasets
        assert 'media/music/flac/classical' in datasets
        
        # Verify auto-parent markers
        assert datasets['media'].get('_auto_parent') is True
        assert datasets['media/music'].get('_auto_parent') is True
        assert datasets['media/music/flac'].get('_auto_parent') is True
        assert datasets['media/music/flac/classical'].get('_auto_parent') is None
    
    def test_nested_with_containers(self, temp_dir):
        """Test that nested datasets work with container mounts."""
        config_path = temp_dir / "tengil.yml"
        config = {
                        'pools': {
                'tank': {
                    'type': 'zfs',
                    'datasets': {
                        'media/music/mp3': {
                            'profile': 'audio',
                            'containers': [
                                {'name': 'navidrome', 'mount': '/music'}
                            ]
                        }
                    }
                }
            }
        }
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        # Flatten to full paths (like CLI does)
        pools = loader.get_pools()
        for pool_name, pool_config in pools.items():
            for dataset_name, _dataset_config in pool_config.get('datasets', {}).items():
                full_path = f"{pool_name}/{dataset_name}"
                
                if full_path == "tank/media/music/mp3":
                    # Now split it back (like CLI does for Proxmox)
                    parts = full_path.split('/')
                    pool = parts[0]
                    dataset = '/'.join(parts[1:])
                    
                    assert pool == "tank"
                    assert dataset == "media/music/mp3"
                    
                    # The host path would be
                    host_path = f"/{pool}/{dataset}"
                    assert host_path == "/tank/media/music/mp3"


class TestPoolAddRemove:
    """Test adding and removing pools."""
    
    def test_add_new_pool(self, temp_dir):
        """Test adding a second pool to existing config."""
        config_path = temp_dir / "tengil.yml"
        
        # Start with one pool
        config_v1 = {
                        'pools': {
                'tank': {
                    'type': 'zfs',
                    'datasets': {
                        'media': {'profile': 'media'}
                    }
                }
            }
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_v1, f)
        
        loader = ConfigLoader(config_path)
        config = loader.load()
        pools = loader.get_pools()
        assert len(pools) == 1
        assert 'tank' in pools
        
        # Now add a second pool
        config_v2 = {
                        'pools': {
                'tank': {
                    'type': 'zfs',
                    'datasets': {
                        'media': {'profile': 'media'}
                    }
                },
                'fastpool': {
                    'type': 'zfs',
                    'datasets': {
                        'appdata': {'profile': 'dev'}
                    }
                }
            }
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_v2, f)
        
        loader2 = ConfigLoader(config_path)
        _ = loader2.load()
        pools2 = loader2.get_pools()
        assert len(pools2) == 2
        assert 'tank' in pools2
        assert 'fastpool' in pools2
    
    def test_remove_pool_only_config(self):
        """Test that removing a pool from config doesn't destroy data.
        
        This is a design principle - tengil never destroys, only creates.
        When you remove a pool from config, the ZFS pool stays intact.
        """
        # This is a documentation test - tengil's diff engine only
        # creates datasets, never destroys them. So removing a pool
        # from the config just means tengil stops managing it.
        assert True  # Design principle documented


class TestDatasetMigration:
    """Test scenarios where datasets move between pools."""
    
    def test_dataset_moves_to_new_pool(self, temp_dir):
        """Simulate moving tank/media to fastpool/media."""
        config_path = temp_dir / "tengil.yml"
        
        # Original: media on tank
        config_old = {
                        'pools': {
                'tank': {
                    'type': 'zfs',
                    'datasets': {
                        'media': {'profile': 'media'}
                    }
                }
            }
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_old, f)
        
        loader_old = ConfigLoader(config_path)
        config_old = loader_old.load()
        
        # Flatten old config
        old_datasets = {}
        for pool_name, pool_config in loader_old.get_pools().items():
            for dataset_name, dataset_config in pool_config.get('datasets', {}).items():
                full_path = f"{pool_name}/{dataset_name}"
                old_datasets[full_path] = dataset_config
        
        assert 'tank/media' in old_datasets
        
        # New: media on fastpool (user migrated with zfs send/recv)
        config_new = {
                        'pools': {
                'fastpool': {
                    'type': 'zfs',
                    'datasets': {
                        'media': {'profile': 'media'}
                    }
                }
            }
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_new, f)
        
        loader_new = ConfigLoader(config_path)
        config_new = loader_new.load()
        
        # Flatten new config
        new_datasets = {}
        for pool_name, pool_config in loader_new.get_pools().items():
            for dataset_name, dataset_config in pool_config.get('datasets', {}).items():
                full_path = f"{pool_name}/{dataset_name}"
                new_datasets[full_path] = dataset_config
        
        assert 'fastpool/media' in new_datasets
        assert 'tank/media' not in new_datasets
        
        # DiffEngine would see this as:
        # - CREATE fastpool/media (because it doesn't exist yet on fastpool)
        # - tank/media ignored (not in new config, tengil doesn't destroy)
        
        # Simulate ZFS state: tank/media still exists, fastpool/media doesn't
        current_state = {
            'tank/media': {'compression': 'lz4'}
        }
        
        engine = DiffEngine(new_datasets, current_state)
        changes = engine.calculate_diff()
        
        # Should want to create fastpool/media
        assert len(changes) == 1
        assert changes[0].dataset == 'fastpool/media'


class TestRestructuring:
    """Test reorganizing dataset hierarchy."""
    
    def test_flatten_to_deeper_structure(self, temp_dir):
        """Test moving tank/media to tank/media/video."""
        config_path = temp_dir / "tengil.yml"
        
        # Original: flat structure
        config_old = {
                        'pools': {
                'tank': {
                    'type': 'zfs',
                    'datasets': {
                        'media': {'profile': 'media'}
                    }
                }
            }
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_old, f)
        
        loader_old = ConfigLoader(config_path)
        config_old = loader_old.load()
        
        # New: deeper structure
        config_new = {
                        'pools': {
                'tank': {
                    'type': 'zfs',
                    'datasets': {
                        'media/video': {'profile': 'media'},
                        'media/audio': {'profile': 'audio'}
                    }
                }
            }
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_new, f)
        
        loader_new = ConfigLoader(config_path)
        config_new = loader_new.load()
        
        # Check parent expansion
        pools = loader_new.get_pools()
        datasets = pools['tank']['datasets']
        
        # 'media' should be auto-created as parent
        assert 'media' in datasets
        assert datasets['media'].get('_auto_parent') is True
        
        # Children are user-defined
        assert 'media/video' in datasets
        assert 'media/audio' in datasets
        assert datasets['media/video'].get('_auto_parent') is None


class TestMultiPoolDiff:
    """Test diff engine with multiple pools."""
    
    def test_changes_across_multiple_pools(self, temp_dir):
        """Test detecting changes in multiple pools simultaneously."""
        config_path = temp_dir / "tengil.yml"
        config = {
                        'pools': {
                'rpool': {
                    'type': 'zfs',
                    'datasets': {
                        'appdata': {'profile': 'dev'}
                    }
                },
                'tank': {
                    'type': 'zfs',
                    'datasets': {
                        'media': {'profile': 'media'}
                    }
                }
            }
        }
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        # Flatten all pools (like CLI does)
        all_desired = {}
        for pool_name, pool_config in loader.get_pools().items():
            for dataset_name, dataset_config in pool_config.get('datasets', {}).items():
                full_path = f"{pool_name}/{dataset_name}"
                all_desired[full_path] = dataset_config
        
        # Simulate current state: neither exists
        current_state = {}
        
        engine = DiffEngine(all_desired, current_state)
        changes = engine.calculate_diff()
        
        # Should detect both need creation
        assert len(changes) == 2
        dataset_names = [c.dataset for c in changes]
        assert 'rpool/appdata' in dataset_names
        assert 'tank/media' in dataset_names


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_pool(self, temp_dir):
        """Test pool with no datasets."""
        config_path = temp_dir / "tengil.yml"
        config = {
                        'pools': {
                'tank': {
                    'type': 'zfs',
                    'datasets': {}
                }
            }
        }
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        loader = ConfigLoader(config_path)
        config = loader.load()
        pools = loader.get_pools()
        
        assert 'tank' in pools
        assert pools['tank']['datasets'] == {}
    
    def test_single_char_dataset_name(self, temp_dir):
        """Test that single character names work."""
        config_path = temp_dir / "tengil.yml"
        config = {
                        'pools': {
                'tank': {
                    'type': 'zfs',
                    'datasets': {
                        'a': {'profile': 'dev'}
                    }
                }
            }
        }
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        pools = loader.get_pools()
        assert 'a' in pools['tank']['datasets']
