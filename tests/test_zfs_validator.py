"""Tests for ZFS validation and recommendations."""

from tengil.core.zfs_validator import Severity, ValidationIssue, ZFSValidator


def test_validate_optimal_recordsize():
    """Test validation of optimal recordsize."""
    validator = ZFSValidator()

    config = {
        'properties': {
            'recordsize': '1M',
            'compression': 'lz4'
        }
    }

    issues = validator.validate_dataset('tank/media', config, profile='media')

    # Should have no errors, maybe info about atime
    errors = [i for i in issues if i.severity == Severity.ERROR]
    assert len(errors) == 0


def test_validate_suboptimal_recordsize():
    """Test warning for suboptimal recordsize."""
    validator = ZFSValidator()

    config = {
        'properties': {
            'recordsize': '128K',  # Suboptimal for media
            'compression': 'lz4'
        }
    }

    issues = validator.validate_dataset('tank/media', config, profile='media')

    # Should warn about suboptimal recordsize
    info_issues = [i for i in issues if i.severity == Severity.INFO and 'recordsize' in i.message.lower()]
    assert len(info_issues) > 0
    assert '1M' in info_issues[0].recommendation


def test_validate_invalid_recordsize():
    """Test error for invalid recordsize."""
    validator = ZFSValidator()

    config = {
        'properties': {
            'recordsize': '100K',  # Not a power of 2
        }
    }

    issues = validator.validate_dataset('tank/media', config, profile='media')

    errors = [i for i in issues if i.severity == Severity.ERROR]
    assert len(errors) > 0
    assert 'power of 2' in errors[0].message


def test_recommend_recordsize_for_profile():
    """Test recordsize recommendation when not set."""
    validator = ZFSValidator()

    config = {
        'properties': {}
    }

    issues = validator.validate_dataset('tank/media', config, profile='media')

    # Should recommend recordsize
    recordsize_recs = [i for i in issues if 'recordsize' in i.message.lower()]
    assert len(recordsize_recs) > 0
    assert '1M' in recordsize_recs[0].message


def test_validate_compression_optimal():
    """Test optimal compression validation."""
    validator = ZFSValidator()

    config = {
        'properties': {
            'compression': 'gzip-9'
        }
    }

    issues = validator.validate_dataset('tank/backups', config, profile='backups')

    # gzip-9 is optimal for backups
    errors = [i for i in issues if i.severity == Severity.ERROR and 'compression' in i.message.lower()]
    assert len(errors) == 0


def test_validate_compression_wrong_profile():
    """Test warning for inappropriate compression."""
    validator = ZFSValidator()

    config = {
        'properties': {
            'compression': 'gzip-9'  # Too slow for media
        }
    }

    issues = validator.validate_dataset('tank/media', config, profile='media')

    # Should warn about CPU-intensive compression on media
    warnings = [i for i in issues if i.severity == Severity.WARNING and 'compression' in i.message.lower()]
    assert len(warnings) > 0


def test_validate_invalid_compression():
    """Test error for invalid compression algorithm."""
    validator = ZFSValidator()

    config = {
        'properties': {
            'compression': 'invalid-algo'
        }
    }

    issues = validator.validate_dataset('tank/media', config, profile='media')

    errors = [i for i in issues if i.severity == Severity.ERROR]
    assert len(errors) > 0
    assert 'Invalid compression' in errors[0].message


def test_recommend_compression_for_profile():
    """Test compression recommendation when not set."""
    validator = ZFSValidator()

    config = {
        'properties': {}
    }

    issues = validator.validate_dataset('tank/backups', config, profile='backups')

    # Should recommend gzip-9 for backups
    comp_recs = [i for i in issues if 'compression' in i.message.lower()]
    assert len(comp_recs) > 0
    assert 'gzip-9' in comp_recs[0].message


def test_warn_about_sync_disabled():
    """Test warning for sync=disabled."""
    validator = ZFSValidator()

    config = {
        'properties': {
            'sync': 'disabled'
        }
    }

    issues = validator.validate_dataset('tank/media', config, profile='media')

    warnings = [i for i in issues if i.severity == Severity.WARNING and 'sync' in i.message.lower()]
    assert len(warnings) > 0
    assert 'data loss' in warnings[0].message.lower()


def test_recommend_atime_off():
    """Test recommendation to disable atime."""
    validator = ZFSValidator()

    config = {
        'properties': {}
    }

    issues = validator.validate_dataset('tank/media', config, profile='media')

    atime_recs = [i for i in issues if 'atime' in i.message.lower()]
    assert len(atime_recs) > 0
    assert 'off' in atime_recs[0].recommendation


def test_check_cross_pool_hardlinks():
    """Test detection of cross-pool hardlink issues."""
    validator = ZFSValidator()

    pools = {
        'tank': {
            'datasets': {
                'downloads': {
                    'containers': [
                        {'name': 'sonarr', 'mount': '/downloads'}
                    ]
                }
            }
        },
        'backup': {
            'datasets': {
                'media': {
                    'containers': [
                        {'name': 'sonarr', 'mount': '/media'}
                    ]
                }
            }
        }
    }

    issues = validator.check_cross_pool_hardlinks(pools)

    errors = [i for i in issues if i.severity == Severity.ERROR]
    assert len(errors) > 0
    assert 'sonarr' in errors[0].message
    assert 'SAME pool' in errors[0].recommendation


def test_no_cross_pool_issues_when_same_pool():
    """Test no issues when containers use same pool."""
    validator = ZFSValidator()

    pools = {
        'tank': {
            'datasets': {
                'downloads': {
                    'containers': [
                        {'name': 'sonarr', 'mount': '/downloads'}
                    ]
                },
                'media': {
                    'containers': [
                        {'name': 'sonarr', 'mount': '/media'}
                    ]
                }
            }
        }
    }

    issues = validator.check_cross_pool_hardlinks(pools)

    errors = [i for i in issues if i.severity == Severity.ERROR and 'sonarr' in i.message]
    assert len(errors) == 0


def test_check_resource_allocation_jellyfin_low():
    """Test warning for insufficient Jellyfin resources."""
    validator = ZFSValidator()

    containers = [
        {
            'name': 'jellyfin',
            'memory': 1024,  # Too low
            'cores': 1  # Too low
        }
    ]

    issues = validator.check_resource_allocation('tank/media', containers, 'media')

    warnings = [i for i in issues if i.severity == Severity.WARNING]
    assert len(warnings) >= 2  # Memory and cores warnings


def test_check_resource_allocation_jellyfin_ok():
    """Test no warnings for adequate Jellyfin resources."""
    validator = ZFSValidator()

    containers = [
        {
            'name': 'jellyfin',
            'memory': 4096,
            'cores': 4
        }
    ]

    issues = validator.check_resource_allocation('tank/media', containers, 'media')

    warnings = [i for i in issues if i.severity == Severity.WARNING]
    assert len(warnings) == 0


def test_check_resource_allocation_ollama():
    """Test Ollama resource validation."""
    validator = ZFSValidator()

    containers = [
        {
            'name': 'ollama',
            'memory': 4096,  # Too low for Ollama
            'cores': 2
        }
    ]

    issues = validator.check_resource_allocation('tank/ai', containers, 'ai')

    warnings = [i for i in issues if i.severity == Severity.WARNING and 'ollama' in i.message.lower()]
    assert len(warnings) > 0
    assert '8192' in warnings[0].message or '8GB' in warnings[0].recommendation


def test_validation_issue_str():
    """Test ValidationIssue string representation."""
    issue = ValidationIssue(
        Severity.WARNING,
        "Test warning",
        dataset="tank/media",
        recommendation="Do something"
    )

    issue_str = str(issue)
    assert "⚠️" in issue_str
    assert "Test warning" in issue_str
    assert "tank/media" in issue_str
    assert "Do something" in issue_str


def test_parse_size():
    """Test size parsing."""
    validator = ZFSValidator()

    assert validator._parse_size('1K') == 1024
    assert validator._parse_size('128K') == 128 * 1024
    assert validator._parse_size('1M') == 1024 * 1024
    assert validator._parse_size('1G') == 1024 * 1024 * 1024
    assert validator._parse_size('1024') == 1024
