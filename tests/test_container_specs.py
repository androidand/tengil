"""Tests for Phase 2+ container management features."""

import pytest
import yaml

from tengil.config.loader import ConfigLoader
from tengil.models.config import ConfigValidationError


class TestContainerAutoCreate:
    """Test Phase 2 auto-create container specifications."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create a temporary directory for test configs."""
        return tmp_path

    def test_basic_auto_create_config(self, temp_dir):
        """Basic auto_create configuration should validate."""
        config = {
                        'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'containers': [
                                {
                                    'name': 'jellyfin',
                                    'vmid': 100,
                                    'auto_create': True,
                                    'template': 'debian-12-standard',
                                    'mount': '/media',
                                    'readonly': True
                                }
                            ]
                        }
                    }
                }
            }
        }

        config_path = temp_dir / "tengil.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)
        result = loader.load()

        container = result['pools']['tank']['datasets']['media']['containers'][0]
        assert container['name'] == 'jellyfin'
        assert container['vmid'] == 100
        assert container['auto_create'] is True
        assert container['template'] == 'debian-12-standard'
        assert container['mount'] == '/media'

    def test_auto_create_with_resources(self, temp_dir):
        """auto_create with custom resources should work."""
        config = {
                        'pools': {
                'tank': {
                    'datasets': {
                        'ai': {
                            'profile': 'media',
                            'containers': [
                                {
                                    'name': 'ollama',
                                    'vmid': 200,
                                    'auto_create': True,
                                    'template': 'debian-12-standard',
                                    'resources': {
                                        'memory': 8192,
                                        'cores': 4,
                                        'disk': '50G'
                                    },
                                    'mount': '/models'
                                }
                            ]
                        }
                    }
                }
            }
        }

        config_path = temp_dir / "tengil.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)
        result = loader.load()

        container = result['pools']['tank']['datasets']['ai']['containers'][0]
        assert container['resources']['memory'] == 8192
        assert container['resources']['cores'] == 4
        assert container['resources']['disk'] == '50G'

    def test_auto_create_with_network(self, temp_dir):
        """auto_create with network config should work."""
        config = {
                        'pools': {
                'tank': {
                    'datasets': {
                        'photos': {
                            'profile': 'media',
                            'containers': [
                                {
                                    'name': 'immich',
                                    'auto_create': True,
                                    'template': 'debian-12-standard',
                                    'network': {
                                        'bridge': 'vmbr0',
                                        'ip': '192.168.1.100/24',
                                        'gateway': '192.168.1.1'
                                    },
                                    'mount': '/photos'
                                }
                            ]
                        }
                    }
                }
            }
        }

        config_path = temp_dir / "tengil.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)
        result = loader.load()

        container = result['pools']['tank']['datasets']['photos']['containers'][0]
        assert container['network']['bridge'] == 'vmbr0'
        assert container['network']['ip'] == '192.168.1.100/24'
        assert container['network']['gateway'] == '192.168.1.1'

    def test_auto_create_requires_template(self, temp_dir):
        """auto_create without template should fail validation."""
        config = {
                        'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'containers': [
                                {
                                    'name': 'jellyfin',
                                    'auto_create': True,
                                    # Missing template!
                                    'mount': '/media'
                                }
                            ]
                        }
                    }
                }
            }
        }

        config_path = temp_dir / "tengil.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)

        with pytest.raises(ConfigValidationError) as exc_info:
            loader.load()

        error_msg = str(exc_info.value)
        assert 'auto_create' in error_msg.lower()
        assert 'template' in error_msg.lower()

    def test_mixed_container_types(self, temp_dir):
        """Mix of existing (Phase 1) and auto-create (Phase 2) containers."""
        config = {
                        'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'containers': [
                                # Phase 1: existing container (no auto_create)
                                {
                                    'name': 'jellyfin',
                                    'vmid': 100,
                                    'mount': '/media'
                                },
                                # Phase 2: auto-create new container
                                {
                                    'name': 'plex',
                                    'vmid': 101,
                                    'auto_create': True,
                                    'template': 'debian-12-standard',
                                    'mount': '/media',
                                    'readonly': True
                                },
                                # String format still works
                                'kodi:/media:ro'
                            ]
                        }
                    }
                }
            }
        }

        config_path = temp_dir / "tengil.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)
        result = loader.load()

        containers = result['pools']['tank']['datasets']['media']['containers']
        assert len(containers) == 3
        
        # Phase 1 container
        assert containers[0]['name'] == 'jellyfin'
        assert 'auto_create' not in containers[0] or not containers[0]['auto_create']
        
        # Phase 2 container
        assert containers[1]['name'] == 'plex'
        assert containers[1]['auto_create'] is True
        
        # String format
        assert containers[2] == 'kodi:/media:ro'


class TestContainerResourceValidation:
    """Test validation of container resource specifications."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        return tmp_path

    def test_invalid_memory_type(self, temp_dir):
        """Memory must be integer (MB)."""
        config = {
                        'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'containers': [
                                {
                                    'name': 'test',
                                    'auto_create': True,
                                    'template': 'debian-12-standard',
                                    'resources': {
                                        'memory': '2GB'  # Should be int!
                                    },
                                    'mount': '/media'
                                }
                            ]
                        }
                    }
                }
            }
        }

        config_path = temp_dir / "tengil.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)
        
        with pytest.raises(ConfigValidationError) as exc_info:
            loader.load()

        assert 'memory' in str(exc_info.value).lower()

    def test_invalid_disk_format(self, temp_dir):
        """Disk must be like '8G' or '512M'."""
        config = {
                        'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'containers': [
                                {
                                    'name': 'test',
                                    'auto_create': True,
                                    'template': 'debian-12-standard',
                                    'resources': {
                                        'disk': '8GB'  # Should be 8G!
                                    },
                                    'mount': '/media'
                                }
                            ]
                        }
                    }
                }
            }
        }

        config_path = temp_dir / "tengil.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)
        
        with pytest.raises(ConfigValidationError) as exc_info:
            loader.load()

        assert 'disk' in str(exc_info.value).lower()

    def test_valid_disk_formats(self, temp_dir):
        """Test all valid disk formats."""
        for disk_size in ['8G', '512M', '100g', '2048m']:
            config = {
                                'pools': {
                    'tank': {
                        'datasets': {
                            'media': {
                                'containers': [
                                    {
                                        'name': 'test',
                                        'auto_create': True,
                                        'template': 'debian-12-standard',
                                        'resources': {
                                            'disk': disk_size
                                        },
                                        'mount': '/media'
                                    }
                                ]
                            }
                        }
                    }
                }
            }

            config_path = temp_dir / f"tengil_{disk_size}.yml"
            with open(config_path, 'w') as f:
                yaml.dump(config, f)

            loader = ConfigLoader(config_path)
            result = loader.load()  # Should not raise

            container = result['pools']['tank']['datasets']['media']['containers'][0]
            assert container['resources']['disk'] == disk_size

    def test_template_resource_values_allowed(self, temp_dir):
        """Jinja-style placeholders for resources should bypass strict int validation."""
        config = {
                        'containers': {
                'jellyfin': {
                    'template': 'debian-12-standard',
                    'memory': '{{ secrets.jellyfin.memory }}',
                    'cores': '{{ secrets.jellyfin.cores }}',
                    'disk_size': '{{ secrets.jellyfin.disk_size }}'
                }
            },
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'containers': [
                                {
                                    'name': 'jellyfin',
                                    'auto_create': True,
                                    'mount': '/media'
                                },
                                {
                                    'name': 'plex',
                                    'auto_create': True,
                                    'template': 'debian-12-standard',
                                    'resources': {
                                        'memory': '{{ secrets.plex.memory }}',
                                        'cores': '{{ secrets.plex.cores }}',
                                        'disk': '{{ secrets.plex.disk }}'
                                    },
                                    'mount': '/plex'
                                }
                            ]
                        }
                    }
                }
            }
        }

        config_path = temp_dir / 'tengil_templates.yml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)
        result = loader.load()

        jellyfin = result['pools']['tank']['datasets']['media']['containers'][0]
        plex = result['pools']['tank']['datasets']['media']['containers'][1]

        assert jellyfin['resources']['memory'] == '{{ secrets.jellyfin.memory }}'
        assert jellyfin['resources']['cores'] == '{{ secrets.jellyfin.cores }}'
        assert jellyfin['resources']['disk'] == '{{ secrets.jellyfin.disk_size }}'

        assert plex['resources']['memory'] == '{{ secrets.plex.memory }}'
        assert plex['resources']['cores'] == '{{ secrets.plex.cores }}'
        assert plex['resources']['disk'] == '{{ secrets.plex.disk }}'


class TestContainerSetupCommands:
    """Test Phase 3 post-install setup commands."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        return tmp_path

    def test_setup_commands_preserved(self, temp_dir):
        """Setup commands should be preserved for Phase 3."""
        config = {
                        'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'containers': [
                                {
                                    'name': 'jellyfin',
                                    'auto_create': True,
                                    'template': 'debian-12-standard',
                                    'mount': '/media',
                                    'setup_commands': [
                                        'apt update',
                                        'apt install -y jellyfin',
                                        'systemctl enable jellyfin'
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        }

        config_path = temp_dir / "tengil.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)
        result = loader.load()

        container = result['pools']['tank']['datasets']['media']['containers'][0]
        assert 'setup_commands' in container
        assert len(container['setup_commands']) == 3
        assert container['setup_commands'][0] == 'apt update'
