"""Tests for consumers config parsing."""
import tempfile
from pathlib import Path

import pytest

from tengil.config.loader import ConfigLoader
from tengil.models.config import ConfigValidationError


def test_parse_consumers_basic():
    """Test basic consumers parsing."""
    config_content = """
mode: converged-nas

pools:
  tank:
    type: zfs
    datasets:
      media:
        profile: media
        consumers:
          - type: container
            name: jellyfin
            access: read
          - type: smb
            name: Media
            access: read
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        # Check dataset was processed
        assert 'pools' in config
        assert 'tank' in config['pools']
        media = config['pools']['tank']['datasets']['media']
        
        # Check consumers were parsed
        assert '_consumers' in media
        assert len(media['_consumers']) == 2
        
        # Check conversion to internal format
        assert 'containers' in media
        assert len(media['containers']) == 1
        assert media['containers'][0]['name'] == 'jellyfin'
        assert media['containers'][0]['readonly'] is True
        
        assert 'shares' in media
        assert 'smb' in media['shares']
        
    finally:
        Path(config_path).unlink()


def test_parse_consumers_write_access():
    """Test consumers with write access."""
    config_content = """
mode: converged-nas

pools:
  tank:
    type: zfs
    datasets:
      uploads:
        profile: default
        consumers:
          - type: container
            name: uploader
            access: write
          - type: smb
            name: Uploads
            access: write
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        uploads = config['pools']['tank']['datasets']['uploads']
        
        # Check write access converted correctly
        assert uploads['containers'][0]['readonly'] is False
        
        smb_config = uploads['shares']['smb'][0]
        assert smb_config['writable'] == 'yes'
        assert smb_config['read only'] == 'no'
        
    finally:
        Path(config_path).unlink()


def test_parse_consumers_mixed_access():
    """Test dataset with both read and write consumers."""
    config_content = """
mode: converged-nas

pools:
  tank:
    type: zfs
    datasets:
      shared:
        profile: default
        consumers:
          - type: container
            name: viewer
            access: read
          - type: container
            name: editor
            access: write
          - type: smb
            name: SharedRead
            access: read
          - type: smb
            name: SharedWrite
            access: write
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        shared = config['pools']['tank']['datasets']['shared']
        
        # Check both containers added
        assert len(shared['containers']) == 2
        viewer = next(c for c in shared['containers'] if c['name'] == 'viewer')
        editor = next(c for c in shared['containers'] if c['name'] == 'editor')
        
        assert viewer['readonly'] is True
        assert editor['readonly'] is False
        
        # Check both SMB shares added
        assert len(shared['shares']['smb']) == 2
        
    finally:
        Path(config_path).unlink()


def test_parse_consumers_custom_mount():
    """Test consumer with custom mount path."""
    config_content = """
mode: converged-nas

pools:
  tank:
    type: zfs
    datasets:
      media:
        profile: media
        consumers:
          - type: container
            name: jellyfin
            access: read
            mount: /custom/media/path
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        media = config['pools']['tank']['datasets']['media']
        
        # Check custom mount path preserved
        assert media['containers'][0]['mount'] == '/custom/media/path'
        
    finally:
        Path(config_path).unlink()


def test_parse_consumers_missing_type():
    """Test consumer validation - missing type."""
    config_content = """
mode: converged-nas

pools:
  tank:
    type: zfs
    datasets:
      media:
        consumers:
          - name: jellyfin
            access: read
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        loader = ConfigLoader(config_path)
        with pytest.raises(ConfigValidationError, match="missing 'type' field"):
            loader.load()
    finally:
        Path(config_path).unlink()


def test_parse_consumers_missing_access():
    """Test consumer validation - missing access."""
    config_content = """
mode: converged-nas

pools:
  tank:
    type: zfs
    datasets:
      media:
        consumers:
          - type: container
            name: jellyfin
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        loader = ConfigLoader(config_path)
        with pytest.raises(ConfigValidationError, match="missing 'access' field"):
            loader.load()
    finally:
        Path(config_path).unlink()


def test_parse_consumers_invalid_access():
    """Test consumer validation - invalid access level."""
    config_content = """
mode: converged-nas

pools:
  tank:
    type: zfs
    datasets:
      media:
        consumers:
          - type: container
            name: jellyfin
            access: readwrite  # Invalid!
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        loader = ConfigLoader(config_path)
        with pytest.raises(ConfigValidationError, match="Invalid access level"):
            loader.load()
    finally:
        Path(config_path).unlink()


def test_parse_consumers_nfs():
    """Test NFS consumer parsing."""
    config_content = """
mode: converged-nas

pools:
  tank:
    type: zfs
    datasets:
      backups:
        profile: backups
        consumers:
          - type: nfs
            name: backup_export
            access: read
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        backups = config['pools']['tank']['datasets']['backups']
        
        # Check NFS share added
        assert 'nfs' in backups['shares']
        assert len(backups['shares']['nfs']) == 1
        assert backups['shares']['nfs'][0]['name'] == 'backup_export'
        assert backups['shares']['nfs'][0]['readonly'] is True
        
    finally:
        Path(config_path).unlink()


def test_consumers_and_manual_config_coexist():
    """Test that consumers can coexist with manual container/share config."""
    config_content = """
mode: converged-nas

pools:
  tank:
    type: zfs
    datasets:
      media:
        profile: media
        
        # New consumers model
        consumers:
          - type: container
            name: jellyfin
            access: read
        
        # Old manual config (still works)
        containers:
          - name: plex
            mount: /media
            readonly: true
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        media = config['pools']['tank']['datasets']['media']
        
        # Both containers should be present
        assert len(media['containers']) == 2
        names = [c['name'] for c in media['containers']]
        assert 'jellyfin' in names
        assert 'plex' in names
        
    finally:
        Path(config_path).unlink()
