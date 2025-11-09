"""Test configuration format validation and compatibility.

Tests ensure that:
1. Correct formats are accepted
2. Deprecated formats show warnings but still work
3. Invalid formats are rejected with clear errors
4. Terminology matches Proxmox/ZFS/Linux standards
"""
import pytest
import tempfile
import yaml
import warnings
from pathlib import Path

from tengil.config.loader import ConfigLoader
from tengil.models.config import ConfigValidationError


@pytest.fixture
def temp_dir():
    """Create temporary directory for test configs."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    import shutil
    shutil.rmtree(temp)


class TestContainerMountFormats:
    """Test container mount point configuration formats.

    Proxmox terminology:
    - Container = LXC container (pct)
    - Mount point = bind mount from host to container
    - mp0, mp1, etc. = Proxmox mount point identifiers
    """

    def test_correct_container_format(self, temp_dir):
        """Standard format with 'name' and 'mount' - Proxmox terminology."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'containers': [
                                {'name': 'jellyfin', 'mount': '/media'},
                                {'name': 'plex', 'mount': '/media', 'readonly': True}
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
        assert len(containers) == 2
        assert containers[0]['name'] == 'jellyfin'
        assert containers[0]['mount'] == '/media'
        assert 'readonly' not in containers[0]  # Default is False
        assert containers[1]['readonly'] is True

    def test_container_mount_path_validation(self, temp_dir):
        """Mount paths must be absolute and follow Linux standards."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'containers': [
                                {'name': 'jellyfin', 'mount': 'relative/path'}  # Invalid!
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

        # Should validate that mount paths are absolute
        with pytest.raises(ConfigValidationError, match="Mount path.*must be absolute"):
            loader.load()

    def test_deprecated_container_path_field(self, temp_dir):
        """Old 'path' field should warn and auto-convert to 'mount'."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'containers': [
                                {'name': 'jellyfin', 'path': '/media'}  # Old field name
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

        # Should emit deprecation warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = loader.load()

            # Check that deprecation warning was issued
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert 'path' in str(w[0].message).lower()
            assert 'mount' in str(w[0].message).lower()

        # Should auto-convert to 'mount'
        containers = result['pools']['tank']['datasets']['media']['containers']
        assert 'mount' in containers[0]
        assert containers[0]['mount'] == '/media'
        assert 'path' not in containers[0]  # Should be removed

    def test_deprecated_container_id_field(self, temp_dir):
        """Old 'id' field should show clear error - we need container name."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'containers': [
                                {'id': 100, 'mount': '/media'}  # Can't auto-convert
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

        # Should emit deprecation warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = loader.load()

            assert len(w) == 1
            assert 'id' in str(w[0].message).lower()
            assert 'name' in str(w[0].message).lower()

    def test_container_string_shorthand(self, temp_dir):
        """String shorthand 'container:/mount' should work - YAML idiomatic."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'containers': [
                                'jellyfin:/media',
                                'plex:/media'
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

        # String format should be preserved (handled by code at runtime)
        containers = result['pools']['tank']['datasets']['media']['containers']
        assert containers[0] == 'jellyfin:/media'
        assert containers[1] == 'plex:/media'


class TestSMBShareFormats:
    """Test SMB/CIFS share configuration formats.

    Samba/SMB terminology:
    - Share = exported directory visible to network clients
    - Path = local filesystem path (auto-calculated from ZFS dataset)
    - Valid users = users allowed to access (Linux user/group)
    """

    def test_correct_smb_format(self, temp_dir):
        """Standard SMB format following Samba conventions."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'shares': {
                                'smb': {
                                    'name': 'Media',
                                    'browseable': 'yes',  # Samba spelling
                                    'guest_ok': False,
                                    'valid_users': '@users'  # Linux group
                                }
                            }
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

        smb = result['pools']['tank']['datasets']['media']['shares']['smb']
        assert smb['name'] == 'Media'
        assert smb['browseable'] == 'yes'  # Samba uses yes/no strings
        assert 'path' not in smb  # Path is auto-calculated

    def test_deprecated_smb_path_parameter(self, temp_dir):
        """SMB 'path' parameter is wrong - it's auto-calculated from dataset."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'shares': {
                                'smb': {
                                    'name': 'Media',
                                    'path': '/tank/media'  # WRONG - auto-calculated!
                                }
                            }
                        }
                    }
                }
            }
        }

        config_path = temp_dir / "tengil.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)

        # Should warn about deprecated path
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = loader.load()

            assert len(w) == 1
            assert 'path' in str(w[0].message).lower()
            assert 'auto-calculated' in str(w[0].message).lower()

        # Path should be removed
        smb = result['pools']['tank']['datasets']['media']['shares']['smb']
        assert 'path' not in smb

    def test_smb_list_format_rejected(self, temp_dir):
        """SMB as list is invalid - should be dict."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'shares': {
                                'smb': [  # WRONG - list format
                                    {'name': 'Media'}
                                ]
                            }
                        }
                    }
                }
            }
        }

        config_path = temp_dir / "tengil.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)

        with pytest.raises(ConfigValidationError, match="SMB.*must be a dict.*not.*list"):
            loader.load()

    def test_smb_at_dataset_level_deprecated(self, temp_dir):
        """SMB should be under 'shares:', not at dataset level."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'smb': {  # OLD - should be under 'shares:'
                                'name': 'Media'
                            }
                        }
                    }
                }
            }
        }

        config_path = temp_dir / "tengil.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)

        # Should warn and auto-fix
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = loader.load()

            assert len(w) == 1
            assert 'shares' in str(w[0].message).lower()

        # Should be moved under 'shares'
        dataset = result['pools']['tank']['datasets']['media']
        assert 'shares' in dataset
        assert 'smb' in dataset['shares']
        assert 'smb' not in dataset  # Removed from top level


class TestNFSExportFormats:
    """Test NFS export configuration formats.

    NFS terminology:
    - Export = shared directory (like /etc/exports)
    - Allowed = client hosts/networks that can mount
    - Options = export options (rw, ro, sync, etc.)
    """

    def test_correct_nfs_format(self, temp_dir):
        """Standard NFS format following /etc/exports conventions."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'shares': {
                                'nfs': {
                                    'allowed': '192.168.1.0/24',  # CIDR notation
                                    'options': 'ro,sync,no_subtree_check'  # NFS options
                                }
                            }
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

        nfs = result['pools']['tank']['datasets']['media']['shares']['nfs']
        assert nfs['allowed'] == '192.168.1.0/24'
        assert nfs['options'] == 'ro,sync,no_subtree_check'

    def test_nfs_boolean_shorthand(self, temp_dir):
        """NFS: true is valid shorthand for default export."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'shares': {
                                'nfs': True  # Shorthand
                            }
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

        # Boolean format is valid
        assert result['pools']['tank']['datasets']['media']['shares']['nfs'] is True

    def test_nfs_wildcard_allowed(self, temp_dir):
        """NFS can use '*' for all hosts - standard NFS syntax."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'shares': {
                                'nfs': {
                                    'allowed': '*',  # All hosts
                                    'options': 'ro,sync'
                                }
                            }
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

        nfs = result['pools']['tank']['datasets']['media']['shares']['nfs']
        assert nfs['allowed'] == '*'


class TestZFSDatasetNaming:
    """Test ZFS dataset naming validation.

    ZFS naming rules:
    - Component max length: 255 chars
    - Valid chars: alphanumeric, dash, underscore, colon, period
    - No leading/trailing slashes
    - No '..' or empty components
    - Reserved names: dump, swap
    """

    def test_valid_dataset_names(self, temp_dir):
        """Valid ZFS dataset names according to OpenZFS spec."""
        valid_names = [
            'media',
            'media-library',
            'app_data',
            'media/movies',
            'media/tv/4k',
            'backup-2024',
            'dataset.with.dots',
        ]

        for dataset_name in valid_names:
            config = {
                'version': 2,
                'pools': {
                    'tank': {
                        'datasets': {
                            dataset_name: {'profile': 'media'}
                        }
                    }
                }
            }

            config_path = temp_dir / f"test_{dataset_name.replace('/', '_')}.yml"
            with open(config_path, 'w') as f:
                yaml.dump(config, f)

            loader = ConfigLoader(config_path)
            result = loader.load()

            # Should not raise
            assert dataset_name in result['pools']['tank']['datasets']

    def test_invalid_dataset_names(self, temp_dir):
        """Invalid ZFS dataset names should be rejected."""
        invalid_cases = [
            ('media@bad', 'invalid characters'),
            ('../escape', 'path traversal'),
            ('media//double', 'empty component'),
            ('/leading', 'leading slash'),
            ('trailing/', 'trailing slash'),
            ('dump', 'reserved name'),
        ]

        for dataset_name, reason in invalid_cases:
            config = {
                'version': 2,
                'pools': {
                    'tank': {
                        'datasets': {
                            dataset_name: {'profile': 'media'}
                        }
                    }
                }
            }

            config_path = temp_dir / f"invalid_{reason.replace(' ', '_')}.yml"
            with open(config_path, 'w') as f:
                yaml.dump(config, f)

            loader = ConfigLoader(config_path)

            with pytest.raises(ConfigValidationError, match=f".*{dataset_name}.*"):
                loader.load()


class TestProxmoxPoolNaming:
    """Test ZFS pool naming validation.

    ZFS pool naming rules:
    - Cannot start with hyphen
    - Cannot start with 'c' + digit (conflicts with device naming)
    - No reserved words: mirror, raidz, spare, log, cache, etc.
    - Valid chars: alphanumeric, dash, underscore, colon, period
    - Max length: 256 chars
    """

    def test_valid_pool_names(self, temp_dir):
        """Valid ZFS pool names."""
        valid_names = ['tank', 'rpool', 'nvme-pool', 'data_backup', 'storage1']

        for pool_name in valid_names:
            config = {
                'version': 2,
                'pools': {
                    pool_name: {
                        'datasets': {'test': {'profile': 'media'}}
                    }
                }
            }

            config_path = temp_dir / f"pool_{pool_name}.yml"
            with open(config_path, 'w') as f:
                yaml.dump(config, f)

            loader = ConfigLoader(config_path)
            result = loader.load()

            assert pool_name in result['pools']

    def test_invalid_pool_names(self, temp_dir):
        """Invalid ZFS pool names should be rejected."""
        invalid_cases = [
            ('-tank', 'starts with hyphen'),
            ('c0', 'starts with c + digit'),
            ('mirror', 'reserved word'),
            ('raidz', 'reserved word'),
        ]

        for pool_name, reason in invalid_cases:
            config = {
                'version': 2,
                'pools': {
                    pool_name: {
                        'datasets': {'test': {'profile': 'media'}}
                    }
                }
            }

            config_path = temp_dir / f"invalid_pool_{reason.replace(' ', '_')}.yml"
            with open(config_path, 'w') as f:
                yaml.dump(config, f)

            loader = ConfigLoader(config_path)

            with pytest.raises(ConfigValidationError):
                loader.load()


class TestPermissionsFormat:
    """Test permissions configuration - Linux/POSIX standards.

    Linux permissions:
    - UID/GID can be numeric or string (user/group name)
    - Mode uses octal notation (0755, 0644, etc.)
    - Octal must be quoted in YAML to preserve leading zero
    """

    def test_correct_permissions_format(self, temp_dir):
        """Standard Linux permissions format."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'permissions': {
                                'uid': 'nobody',  # User name (Linux)
                                'gid': 'users',   # Group name (Linux)
                                'mode': '0755'    # Octal mode (quoted!)
                            }
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

        perms = result['pools']['tank']['datasets']['media']['permissions']
        assert perms['uid'] == 'nobody'
        assert perms['gid'] == 'users'
        assert perms['mode'] == '0755'  # String with leading zero

    def test_numeric_uid_gid(self, temp_dir):
        """Numeric UID/GID are valid."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'permissions': {
                                'uid': 1000,  # Numeric UID
                                'gid': 1000,  # Numeric GID
                                'mode': '0755'
                            }
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

        perms = result['pools']['tank']['datasets']['media']['permissions']
        assert perms['uid'] == 1000
        assert perms['gid'] == 1000


class TestBackwardsCompatibility:
    """Test that old configs work with deprecation warnings."""

    def test_multiple_deprecations_all_warned(self, temp_dir):
        """Config with multiple deprecated formats shows all warnings."""
        config = {
            'version': 2,
            'pools': {
                'tank': {
                    'datasets': {
                        'media': {
                            'profile': 'media',
                            'containers': [
                                {'name': 'jellyfin', 'path': '/media'}  # Deprecated
                            ],
                            'smb': {  # Deprecated location
                                'name': 'Media',
                                'path': '/tank/media'  # Deprecated param
                            }
                        }
                    }
                }
            }
        }

        config_path = temp_dir / "tengil.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(config_path)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = loader.load()

            # Should have multiple warnings
            assert len(w) >= 2

            # All should be DeprecationWarnings
            for warning in w:
                assert issubclass(warning.category, DeprecationWarning)
