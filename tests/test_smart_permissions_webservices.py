"""Tests for Smart Defaults with generic webservices and Node.js apps.

This is where we test the rainbow magic! 🌈🦄
"""

import pytest
from tengil.core.smart_permissions import (
    apply_smart_defaults,
    infer_container_access,
    validate_permissions,
    SmartPermissionEvent,
)


class TestNodeJSWebservices:
    """Test Node.js and generic webservice scenarios."""

    def test_nodejs_api_appdata_profile_readwrite(self):
        """Node.js API on appdata profile gets readwrite by default."""
        config = {
            'profile': 'appdata',
            'containers': [
                {'name': 'my-nodejs-api', 'mount': '/app'}
            ],
            'shares': {
                'smb': {'name': 'WebServices'}
            }
        }
        
        processed = apply_smart_defaults(config, 'webservices')
        
        # Container should get readwrite (appdata profile default)
        container = processed['containers'][0]
        assert "readonly" not in container or container["readonly"] is False
        
        # SMB should inherit readwrite permissions
        assert processed['shares']['smb']['writable'] == 'yes'
        assert processed['shares']['smb']['read only'] == 'no'

    def test_static_site_media_profile_readonly(self):
        """Static site on media profile gets readonly by default."""
        config = {
            'profile': 'media',
            'containers': [
                {'name': 'nginx-static', 'mount': '/www'}
            ],
            'shares': {
                'smb': {'name': 'StaticSites'}
            }
        }
        
        processed = apply_smart_defaults(config, 'static_sites')
        
        # Container should get readonly (media profile default)
        assert processed['containers'][0]['readonly'] == True
        
        # SMB should inherit readonly permissions
        assert processed['shares']['smb']['writable'] == 'no'
        assert processed['shares']['smb']['read only'] == 'yes'

    def test_dev_environment_readwrite(self):
        """Development environment gets readwrite by default."""
        config = {
            'profile': 'dev',
            'containers': [
                {'name': 'vscode-server', 'mount': '/workspace'},
                {'name': 'custom-build-tool', 'mount': '/build'}
            ]
        }
        
        processed = apply_smart_defaults(config, 'dev_workspace')
        
        # Both containers should get readwrite (dev profile default)
        for container in processed['containers']:
            assert "readonly" not in container or container["readonly"] is False

    def test_explicit_override_wins(self):
        """Explicit readonly setting overrides profile default."""
        config = {
            'profile': 'appdata',  # Would default to readwrite
            'containers': [
                {
                    'name': 'my-readonly-service',
                    'mount': '/data',
                    'readonly': True  # Explicit override
                }
            ]
        }
        
        processed = apply_smart_defaults(config, 'services')
        
        # Explicit setting should be preserved
        assert processed['containers'][0]['readonly'] == True

    def test_known_container_overrides_profile(self):
        """Known container patterns override profile defaults."""
        config = {
            'profile': 'appdata',  # Would default to readwrite
            'containers': [
                {'name': 'jellyfin', 'mount': '/media'},  # Known readonly
                {'name': 'radarr', 'mount': '/media'},    # Known readwrite
                {'name': 'unknown-app', 'mount': '/data'} # Falls back to profile
            ]
        }
        
        processed = apply_smart_defaults(config, 'mixed_apps')
        
        # Known patterns should override profile
        assert processed['containers'][0]['readonly'] == True   # jellyfin
        # radarr and unknown-app should be readwrite (no readonly key or False)
        for i in [1, 2]:
            container = processed['containers'][i]
            assert "readonly" not in container or container["readonly"] is False


class TestProfileDefaults:
    """Test different profile behaviors."""

    def test_media_profile_readonly_default(self):
        """Media profile defaults unknown apps to readonly."""
        readonly = infer_container_access('unknown-app', 'media')
        assert readonly == True

    def test_appdata_profile_readwrite_default(self):
        """Appdata profile defaults unknown apps to readwrite."""
        readonly = infer_container_access('unknown-app', 'appdata')
        assert readonly == False

    def test_dev_profile_readwrite_default(self):
        """Dev profile defaults unknown apps to readwrite."""
        readonly = infer_container_access('unknown-app', 'dev')
        assert readonly == False

    def test_downloads_profile_readwrite_default(self):
        """Downloads profile defaults unknown apps to readwrite."""
        readonly = infer_container_access('unknown-app', 'downloads')
        assert readonly == False

    def test_photos_profile_readonly_default(self):
        """Photos profile defaults unknown apps to readonly."""
        readonly = infer_container_access('unknown-app', 'photos')
        assert readonly == True

    def test_unknown_profile_conservative_default(self):
        """Unknown profile defaults to conservative readonly."""
        readonly = infer_container_access('unknown-app', 'weird-profile')
        assert readonly == True


class TestFuzzyMatching:
    """Test fuzzy matching for container variants."""

    def test_jellyfin_variants_readonly(self):
        """Jellyfin variants should be detected as readonly."""
        variants = [
            'jellyfin-nightly',
            'jellyfin-unstable', 
            'my-jellyfin-server',
            'jellyfin-custom'
        ]
        
        for variant in variants:
            readonly = infer_container_access(variant, 'appdata')
            assert readonly == True, f"{variant} should be readonly"

    def test_radarr_variants_readwrite(self):
        """Radarr variants should be detected as readwrite."""
        variants = [
            'radarr-nightly',
            'radarr-develop',
            'my-radarr-instance',
            'radarr-4k'
        ]
        
        for variant in variants:
            readonly = infer_container_access(variant, 'media')
            assert readonly == False, f"{variant} should be readwrite"


class TestMixedAccessValidation:
    """Test validation warnings for mixed access patterns."""

    def test_mixed_access_generates_warning(self):
        """Mixed readonly/readwrite containers should generate warning."""
        config = {
            'containers': [
                {'name': 'jellyfin', 'readonly': True},
                {'name': 'radarr', 'readonly': False}
            ]
        }
        
        warnings = validate_permissions(config, 'tank/media')
        
        assert len(warnings) == 1
        assert 'Mixed access' in warnings[0]
        assert 'jellyfin' in warnings[0]
        assert 'radarr' in warnings[0]

    def test_consistent_access_no_warning(self):
        """Consistent access patterns should not generate warnings."""
        readonly_config = {
            'containers': [
                {'name': 'jellyfin', 'readonly': True},
                {'name': 'plex', 'readonly': True}
            ]
        }
        
        readwrite_config = {
            'containers': [
                {'name': 'radarr', 'readonly': False},
                {'name': 'sonarr', 'readonly': False}
            ]
        }
        
        assert validate_permissions(readonly_config, 'tank/media') == []
        assert validate_permissions(readwrite_config, 'tank/downloads') == []


class TestSMBPermissionPropagation:
    """Test SMB share permission inheritance."""

    def test_readwrite_containers_make_writable_smb(self):
        """Readwrite containers should make SMB shares writable."""
        config = {
            'profile': 'appdata',
            'containers': [
                {'name': 'my-api', 'mount': '/app'}  # Will be readwrite
            ],
            'shares': {
                'smb': {'name': 'API'}
            }
        }
        
        processed = apply_smart_defaults(config, 'api')
        
        assert processed['shares']['smb']['writable'] == 'yes'
        assert processed['shares']['smb']['read only'] == 'no'

    def test_readonly_containers_make_readonly_smb(self):
        """Readonly containers should make SMB shares readonly."""
        config = {
            'profile': 'media',
            'containers': [
                {'name': 'nginx-static', 'mount': '/www'}  # Will be readonly
            ],
            'shares': {
                'smb': {'name': 'Static'}
            }
        }
        
        processed = apply_smart_defaults(config, 'static')
        
        assert processed['shares']['smb']['writable'] == 'no'
        assert processed['shares']['smb']['read only'] == 'yes'

    def test_mixed_containers_most_permissive_wins(self):
        """Mixed access containers should make SMB writable (most permissive)."""
        config = {
            'containers': [
                {'name': 'jellyfin', 'readonly': True},   # readonly
                {'name': 'radarr', 'readonly': False}     # readwrite
            ],
            'shares': {
                'smb': {'name': 'Mixed'}
            }
        }
        
        processed = apply_smart_defaults(config, 'mixed')
        
        # Most permissive (readwrite) should win
        assert processed['shares']['smb']['writable'] == 'yes'
        assert processed['shares']['smb']['read only'] == 'no'


class TestRealWorldScenarios:
    """Test realistic homelab scenarios."""

    def test_complete_media_server_setup(self):
        """Complete media server with automation."""
        config = {
            'profile': 'media',
            'containers': [
                {'name': 'jellyfin', 'mount': '/media'},      # Known readonly
                {'name': 'radarr', 'mount': '/media'},        # Known readwrite  
                {'name': 'sonarr', 'mount': '/media'},        # Known readwrite
                {'name': 'custom-indexer', 'mount': '/media'} # Unknown + media = readonly
            ],
            'shares': {
                'smb': {'name': 'Media'}
            }
        }
        
        processed = apply_smart_defaults(config, 'media')
        
        # Check individual container permissions
        containers = {c['name']: c.get('readonly', False) for c in processed['containers']}
        assert containers['jellyfin'] == True      # Known readonly
        assert containers['radarr'] == False      # Known readwrite
        assert containers['sonarr'] == False      # Known readwrite  
        assert containers['custom-indexer'] == True  # Unknown + media profile
        
        # SMB should be writable (has readwrite containers)
        assert processed['shares']['smb']['writable'] == 'yes'

    def test_development_workspace(self):
        """Development workspace with various tools."""
        config = {
            'profile': 'dev',
            'containers': [
                {'name': 'vscode-server', 'mount': '/workspace'},
                {'name': 'nodejs-dev', 'mount': '/app'},
                {'name': 'postgres', 'mount': '/data'},  # Known readwrite
                {'name': 'nginx-proxy', 'mount': '/config'}
            ]
        }
        
        processed = apply_smart_defaults(config, 'dev_workspace')
        
        # All should be readwrite (dev profile + known patterns)
        for container in processed['containers']:
            assert "readonly" not in container or container["readonly"] is False

    def test_backup_storage_readonly(self):
        """Backup storage should default to readonly."""
        config = {
            'profile': 'backups',
            'containers': [
                {'name': 'backup-viewer', 'mount': '/backups'},
                {'name': 'restore-tool', 'mount': '/backups'}
            ]
        }
        
        processed = apply_smart_defaults(config, 'backups')
        
        # Backup profile should default to readonly
        for container in processed['containers']:
            assert container['readonly'] == True