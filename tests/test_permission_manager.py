"""Tests for unified permission management."""

import pytest

from tengil.core.permission_manager import (
    AccessLevel,
    ConsumerType,
    PermissionConflict,
    PermissionManager,
)


def test_register_dataset():
    """Test registering a dataset."""
    pm = PermissionManager(mock=True)
    
    perm_set = pm.register_dataset("tank/media")
    
    assert perm_set.dataset_path == "tank/media"
    assert perm_set.owner_user == "root"
    assert perm_set.owner_group == "root"
    assert len(perm_set.consumers) == 0


def test_add_container_consumer():
    """Test adding a container consumer."""
    pm = PermissionManager(mock=True)
    pm.register_dataset("tank/media")
    
    consumer = pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "jellyfin",
        AccessLevel.READ
    )
    
    assert consumer.name == "jellyfin"
    assert consumer.type == ConsumerType.CONTAINER
    assert consumer.access == AccessLevel.READ
    assert consumer.readonly is True


def test_add_write_consumer():
    """Test adding a write-access consumer."""
    pm = PermissionManager(mock=True)
    pm.register_dataset("tank/photos")
    
    consumer = pm.add_consumer(
        "tank/photos",
        ConsumerType.CONTAINER,
        "immich",
        AccessLevel.WRITE
    )
    
    assert consumer.access == AccessLevel.WRITE
    assert consumer.readonly is False


def test_multiple_consumers_same_dataset():
    """Test multiple consumers on same dataset."""
    pm = PermissionManager(mock=True)
    pm.register_dataset("tank/media")
    
    # Add read consumer
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "jellyfin",
        AccessLevel.READ
    )
    
    # Add write consumer
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "immich",
        AccessLevel.WRITE
    )
    
    # Add SMB share
    pm.add_consumer(
        "tank/media",
        ConsumerType.SHARE_SMB,
        "Media",
        AccessLevel.READ
    )
    
    perm_set = pm.permission_sets["tank/media"]
    assert len(perm_set.consumers) == 3
    assert len(perm_set.container_consumers) == 2
    assert len(perm_set.smb_consumers) == 1


def test_conflict_detection():
    """Test permission conflict detection."""
    pm = PermissionManager(mock=True)
    pm.register_dataset("tank/media")
    
    # Add container with read access
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "jellyfin",
        AccessLevel.READ
    )
    
    # Try to add same container with different access
    with pytest.raises(PermissionConflict):
        pm.add_consumer(
            "tank/media",
            ConsumerType.CONTAINER,
            "jellyfin",
            AccessLevel.WRITE
        )


def test_container_mount_flags():
    """Test getting mount flags for containers."""
    pm = PermissionManager(mock=True)
    pm.register_dataset("tank/media")
    
    # Add read-only container
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "jellyfin",
        AccessLevel.READ
    )
    
    # Add read-write container
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "immich",
        AccessLevel.WRITE
    )
    
    # Check jellyfin flags
    flags = pm.get_container_mount_flags("tank/media", "jellyfin")
    assert flags["readonly"] is True
    
    # Check immich flags
    flags = pm.get_container_mount_flags("tank/media", "immich")
    assert flags["readonly"] is False


def test_zfs_acl_commands():
    """Test ZFS ACL command generation."""
    pm = PermissionManager(mock=True)
    pm.register_dataset("tank/media", owner_user="media", owner_group="media")
    
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "jellyfin",
        AccessLevel.READ
    )
    
    commands = pm.get_zfs_acl_commands("tank/media")
    
    assert len(commands) > 0
    assert any("chown media:media" in cmd for cmd in commands)
    assert any("chmod" in cmd for cmd in commands)


def test_zfs_acl_write_permissions():
    """Test ZFS ACL generation for write access."""
    pm = PermissionManager(mock=True)
    pm.register_dataset("tank/photos")
    
    # Add write consumer
    pm.add_consumer(
        "tank/photos",
        ConsumerType.CONTAINER,
        "immich",
        AccessLevel.WRITE
    )
    
    commands = pm.get_zfs_acl_commands("tank/photos")
    
    # Should set more permissive permissions for writers
    assert any("chmod 775" in cmd for cmd in commands)


def test_smb_share_config():
    """Test SMB share configuration generation."""
    pm = PermissionManager(mock=True)
    pm.register_dataset("tank/media")
    
    pm.add_consumer(
        "tank/media",
        ConsumerType.SHARE_SMB,
        "Media",
        AccessLevel.READ
    )
    
    config = pm.get_smb_share_config("tank/media", "Media")
    
    assert config["path"] == "/tank/media"
    assert config["read only"] == "yes"
    assert config["writable"] == "no"


def test_smb_share_config_write():
    """Test SMB share configuration for write access."""
    pm = PermissionManager(mock=True)
    pm.register_dataset("tank/uploads")
    
    pm.add_consumer(
        "tank/uploads",
        ConsumerType.SHARE_SMB,
        "Uploads",
        AccessLevel.WRITE
    )
    
    config = pm.get_smb_share_config("tank/uploads", "Uploads")
    
    assert config["read only"] == "no"
    assert config["writable"] == "yes"


def test_validate_mixed_access():
    """Test validation warns about mixed read/write access."""
    pm = PermissionManager(mock=True)
    pm.register_dataset("tank/media")
    
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "jellyfin",
        AccessLevel.READ
    )
    
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "immich",
        AccessLevel.WRITE
    )
    
    issues = pm.validate_all()
    
    assert len(issues) > 0
    assert "Mixed access" in issues[0]
    assert "jellyfin" in issues[0] or "immich" in issues[0]


def test_permission_summary():
    """Test generating permission summary."""
    pm = PermissionManager(mock=True)
    pm.register_dataset("tank/media")
    
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "jellyfin",
        AccessLevel.READ
    )
    
    pm.add_consumer(
        "tank/media",
        ConsumerType.SHARE_SMB,
        "Media",
        AccessLevel.READ
    )
    
    summary = pm.generate_summary()
    
    assert "tank/media" in summary
    assert "jellyfin" in summary
    assert "Media" in summary
    assert "ro" in summary or "read-only" in summary


def test_needs_write_access():
    """Test detecting if dataset needs write access."""
    pm = PermissionManager(mock=True)
    perm_set = pm.register_dataset("tank/media")
    
    # No consumers - no write needed
    assert perm_set.needs_write_access is False
    
    # Add read-only consumer
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "jellyfin",
        AccessLevel.READ
    )
    assert perm_set.needs_write_access is False
    
    # Add write consumer
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "immich",
        AccessLevel.WRITE
    )
    assert perm_set.needs_write_access is True


def test_auto_register_on_add_consumer():
    """Test that datasets are auto-registered when adding consumer."""
    pm = PermissionManager(mock=True)
    
    # Add consumer without registering dataset first
    pm.add_consumer(
        "tank/photos",
        ConsumerType.CONTAINER,
        "immich",
        AccessLevel.WRITE
    )
    
    # Dataset should be auto-registered
    assert "tank/photos" in pm.permission_sets
    perm_set = pm.permission_sets["tank/photos"]
    assert len(perm_set.consumers) == 1


def test_add_consumer_idempotent():
    """Adding identical consumers should avoid duplicates."""
    pm = PermissionManager(mock=True)
    pm.register_dataset("tank/media")
    
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "jellyfin",
        AccessLevel.READ
    )
    
    # Second registration should be ignored
    pm.add_consumer(
        "tank/media",
        ConsumerType.CONTAINER,
        "jellyfin",
        AccessLevel.READ
    )
    
    perm_set = pm.permission_sets["tank/media"]
    assert len(perm_set.consumers) == 1


def test_load_from_config_registers_consumers():
    """load_from_config registers datasets, owners, and consumers."""
    pm = PermissionManager(mock=True)
    datasets = {
        "tank/media": {
            "permissions": {"uid": "media", "gid": "media"},
            "consumers": [
                {"type": "container", "name": "jellyfin", "access": "read"},
                {"type": "smb", "name": "Media", "access": "write"},
            ],
        }
    }
    
    pm.load_from_config(datasets)
    
    assert "tank/media" in pm.permission_sets
    perm_set = pm.permission_sets["tank/media"]
    assert perm_set.owner_user == "media"
    assert perm_set.owner_group == "media"
    assert len(perm_set.consumers) == 2
    smb_consumer = next(c for c in perm_set.consumers if c.type == ConsumerType.SHARE_SMB)
    assert smb_consumer.name == "Media"
    assert smb_consumer.access == AccessLevel.WRITE
