"""Tests for smart permission validation and warnings system."""

import pytest
from tengil.core.smart_permissions import (
    validate_permissions,
    detect_permission_issues,
    SmartPermissionEvent,
)


class TestValidatePermissions:
    """Test permission validation for individual datasets."""

    def test_mixed_access_generates_warning(self):
        """Mixed readonly/readwrite containers should generate warning."""
        config = {
            'profile': 'media',
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
        assert 'Consider separate datasets' in warnings[0]

    def test_consistent_readonly_no_warning(self):
        """Consistent readonly access should not generate warnings."""
        config = {
            'profile': 'media',
            'containers': [
                {'name': 'jellyfin', 'readonly': True},
                {'name': 'plex', 'readonly': True}
            ]
        }
        
        warnings = validate_permissions(config, 'tank/media')
        assert warnings == []

    def test_consistent_readwrite_no_warning(self):
        """Consistent readwrite access should not generate warnings."""
        config = {
            'profile': 'appdata',
            'containers': [
                {'name': 'radarr', 'readonly': False},
                {'name': 'sonarr', 'readonly': False}
            ]
        }
        
        warnings = validate_permissions(config, 'tank/downloads')
        assert warnings == []

    def test_profile_mismatch_warning(self):
        """Known readwrite containers on readonly profiles should warn."""
        config = {
            'profile': 'media',  # Suggests readonly
            'containers': [
                {'name': 'radarr'}  # Known readwrite container, no explicit readonly
            ]
        }
        
        warnings = validate_permissions(config, 'tank/media')
        
        assert len(warnings) == 1
        assert 'Profile mismatch' in warnings[0]
        assert 'radarr' in warnings[0]
        assert 'appdata' in warnings[0]

    def test_explicit_override_no_mismatch_warning(self):
        """Explicit readonly settings should not trigger mismatch warnings."""
        config = {
            'profile': 'media',
            'containers': [
                {'name': 'radarr', 'readonly': False}  # Explicit override
            ]
        }
        
        warnings = validate_permissions(config, 'tank/media')
        
        # Should only warn about mixed access, not profile mismatch
        assert len(warnings) == 0  # No other containers, so no mixed access

    def test_multiple_warnings_combined(self):
        """Multiple issues should generate multiple warnings."""
        config = {
            'profile': 'media',
            'containers': [
                {'name': 'jellyfin'},  # Will be readonly (good)
                {'name': 'radarr'},    # Will be readwrite (mismatch + mixed)
                {'name': 'sonarr'}     # Will be readwrite (mismatch + mixed)
            ]
        }
        
        warnings = validate_permissions(config, 'tank/media')
        
        # Should have mixed access warning + profile mismatch warnings
        assert len(warnings) >= 2
        warning_text = ' '.join(warnings)
        assert 'Mixed access' in warning_text
        assert 'Profile mismatch' in warning_text


class TestDetectPermissionIssues:
    """Test comprehensive permission issue detection across pools."""

    def test_missing_profile_warning(self):
        """Datasets with containers but no profile should warn."""
        pools_config = {
            'tank': {
                'datasets': {
                    'media': {
                        # Missing profile
                        'containers': [
                            {'name': 'jellyfin', 'mount': '/media'}
                        ]
                    }
                }
            }
        }
        
        warnings, suggestions = detect_permission_issues(pools_config)
        
        assert len(warnings) == 1
        assert 'No profile specified' in warnings[0]
        assert 'tank/media' in warnings[0]

    def test_nodejs_app_suggestion(self):
        """Node.js apps on readonly profiles should get suggestions."""
        pools_config = {
            'tank': {
                'datasets': {
                    'webservices': {
                        'profile': 'media',  # Readonly profile
                        'containers': [
                            {'name': 'my-nodejs-api', 'mount': '/app'}
                        ]
                    }
                }
            }
        }
        
        warnings, suggestions = detect_permission_issues(pools_config)
        
        assert len(suggestions) == 1
        assert 'web app' in suggestions[0]
        assert 'appdata' in suggestions[0]
        assert 'my-nodejs-api' in suggestions[0]

    def test_web_app_variants_detected(self):
        """Various web app naming patterns should be detected."""
        web_app_names = [
            'my-node-server',
            'api-gateway', 
            'web-frontend',
            'app-backend',
            'nodejs-service'
        ]
        
        for app_name in web_app_names:
            pools_config = {
                'tank': {
                    'datasets': {
                        'services': {
                            'profile': 'media',
                            'containers': [
                                {'name': app_name, 'mount': '/app'}
                            ]
                        }
                    }
                }
            }
            
            warnings, suggestions = detect_permission_issues(pools_config)
            
            assert len(suggestions) >= 1, f"Should suggest profile change for {app_name}"
            assert 'web app' in suggestions[0] or 'app' in suggestions[0]

    def test_multiple_pools_and_datasets(self):
        """Should detect issues across multiple pools and datasets."""
        pools_config = {
            'tank': {
                'datasets': {
                    'media': {
                        'profile': 'media',
                        'containers': [
                            {'name': 'jellyfin'},
                            {'name': 'radarr'}  # Mismatch
                        ]
                    },
                    'apps': {
                        # Missing profile
                        'containers': [
                            {'name': 'portainer'}
                        ]
                    }
                }
            },
            'nvme': {
                'datasets': {
                    'webservices': {
                        'profile': 'photos',  # Readonly profile
                        'containers': [
                            {'name': 'my-api-server'}  # Should suggest appdata
                        ]
                    }
                }
            }
        }
        
        warnings, suggestions = detect_permission_issues(pools_config)
        
        # Should find multiple issues
        assert len(warnings) >= 2  # Mixed access + missing profile
        assert len(suggestions) >= 1  # Web app suggestion
        
        warning_text = ' '.join(warnings)
        suggestion_text = ' '.join(suggestions)
        
        assert 'tank/media' in warning_text
        assert 'tank/apps' in warning_text
        assert 'nvme/webservices' in suggestion_text

    def test_no_issues_returns_empty(self):
        """Well-configured pools should return no warnings or suggestions."""
        pools_config = {
            'tank': {
                'datasets': {
                    'media': {
                        'profile': 'media',
                        'containers': [
                            {'name': 'jellyfin', 'readonly': True},
                            {'name': 'plex', 'readonly': True}
                        ]
                    },
                    'downloads': {
                        'profile': 'downloads',
                        'containers': [
                            {'name': 'radarr', 'readonly': False},
                            {'name': 'sonarr', 'readonly': False}
                        ]
                    }
                }
            }
        }
        
        warnings, suggestions = detect_permission_issues(pools_config)
        
        assert warnings == []
        assert suggestions == []

    def test_empty_pools_config(self):
        """Empty or malformed config should not crash."""
        test_configs = [
            {},
            {'tank': {}},
            {'tank': {'datasets': {}}},
            {'tank': {'datasets': {'media': {}}}},
        ]
        
        for config in test_configs:
            warnings, suggestions = detect_permission_issues(config)
            # Should not crash, may return empty results
            assert isinstance(warnings, list)
            assert isinstance(suggestions, list)


class TestWarningMessages:
    """Test that warning messages are helpful and actionable."""

    def test_mixed_access_warning_format(self):
        """Mixed access warnings should be clear and actionable."""
        config = {
            'containers': [
                {'name': 'jellyfin', 'readonly': True},
                {'name': 'radarr', 'readonly': False}
            ]
        }
        
        warnings = validate_permissions(config, 'tank/media')
        warning = warnings[0]
        
        # Should include dataset name
        assert 'tank/media' in warning
        
        # Should list specific containers
        assert 'jellyfin' in warning
        assert 'radarr' in warning
        
        # Should provide actionable advice
        assert 'separate datasets' in warning or 'explicit readonly' in warning

    def test_profile_mismatch_warning_format(self):
        """Profile mismatch warnings should suggest solutions."""
        config = {
            'profile': 'media',
            'containers': [
                {'name': 'radarr'}
            ]
        }
        
        warnings = validate_permissions(config, 'tank/media')
        warning = warnings[0]
        
        # Should identify the problem
        assert 'Profile mismatch' in warning
        assert 'radarr' in warning
        
        # Should suggest solutions
        assert 'appdata' in warning or 'readonly: false' in warning

    def test_missing_profile_warning_format(self):
        """Missing profile warnings should explain the benefit."""
        pools_config = {
            'tank': {
                'datasets': {
                    'media': {
                        'containers': [{'name': 'jellyfin'}]
                    }
                }
            }
        }
        
        warnings, _ = detect_permission_issues(pools_config)
        warning = warnings[0]
        
        # Should identify the dataset
        assert 'tank/media' in warning
        
        # Should explain what to add
        assert 'profile:' in warning
        assert 'smart defaults' in warning

    def test_suggestion_format(self):
        """Suggestions should be helpful and non-intrusive."""
        pools_config = {
            'tank': {
                'datasets': {
                    'services': {
                        'profile': 'media',
                        'containers': [
                            {'name': 'my-nodejs-api'}
                        ]
                    }
                }
            }
        }
        
        _, suggestions = detect_permission_issues(pools_config)
        suggestion = suggestions[0]
        
        # Should use friendly emoji/formatting
        assert '💡' in suggestion
        
        # Should identify the container
        assert 'my-nodejs-api' in suggestion
        
        # Should suggest specific action
        assert 'appdata' in suggestion