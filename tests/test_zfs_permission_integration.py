"""Integration tests for ZFSManager with PermissionManager."""
from tengil.core.permission_manager import AccessLevel, ConsumerType, PermissionManager
from tengil.core.zfs_manager import ZFSManager


def test_zfs_creates_dataset_with_permissions():
    """Test that creating a dataset automatically applies permissions."""
    perm_mgr = PermissionManager(mock=True)
    zfs_mgr = ZFSManager(mock=True, permission_manager=perm_mgr)
    
    # Register dataset with consumers
    perm_mgr.register_dataset("tank/media")
    perm_mgr.add_consumer("tank/media", ConsumerType.CONTAINER, "jellyfin", AccessLevel.READ)
    perm_mgr.add_consumer("tank/media", ConsumerType.SHARE_SMB, "Media", AccessLevel.READ)
    
    # Create dataset - should automatically apply permissions
    properties = {
        "recordsize": "1M",
        "compression": "lz4"
    }
    
    success = zfs_mgr.create_dataset("tank/media", properties)
    assert success
    
    # Verify permissions would be applied
    acl_commands = perm_mgr.get_zfs_acl_commands("tank/media")
    assert len(acl_commands) > 0  # Should have chown/chmod commands


def test_zfs_syncs_properties_and_permissions():
    """Test that syncing existing dataset also applies permissions."""
    perm_mgr = PermissionManager(mock=True)
    zfs_mgr = ZFSManager(mock=True, permission_manager=perm_mgr)
    
    # First create the dataset
    properties = {"recordsize": "1M"}
    zfs_mgr.create_dataset("tank/movies", properties)
    
    # Now add consumers and "re-create" (will sync instead)
    perm_mgr.register_dataset("tank/movies")
    perm_mgr.add_consumer("tank/movies", ConsumerType.CONTAINER, "plex", AccessLevel.READ)
    
    # Create again - should sync properties and apply permissions
    success = zfs_mgr.create_dataset("tank/movies", properties)
    assert success
    
    # Verify permissions configured
    acl_commands = perm_mgr.get_zfs_acl_commands("tank/movies")
    assert len(acl_commands) > 0


def test_zfs_without_permission_manager():
    """Test that ZFSManager still works without PermissionManager."""
    zfs_mgr = ZFSManager(mock=True, permission_manager=None)
    
    properties = {"recordsize": "128K"}
    success = zfs_mgr.create_dataset("tank/data", properties)
    assert success


def test_multiple_consumers_different_access():
    """Test permissions with multiple consumers having different access levels."""
    perm_mgr = PermissionManager(mock=True)
    zfs_mgr = ZFSManager(mock=True, permission_manager=perm_mgr)
    
    # Register dataset with mixed read/write consumers
    perm_mgr.register_dataset("tank/shared")
    perm_mgr.add_consumer("tank/shared", ConsumerType.CONTAINER, "app1", AccessLevel.READ)
    perm_mgr.add_consumer("tank/shared", ConsumerType.CONTAINER, "app2", AccessLevel.WRITE)
    perm_mgr.add_consumer("tank/shared", ConsumerType.SHARE_SMB, "Shared", AccessLevel.WRITE)
    
    # Create dataset
    success = zfs_mgr.create_dataset("tank/shared", {"recordsize": "128K"})
    assert success
    
    # Verify permissions computed correctly (most permissive = 775)
    acl_commands = perm_mgr.get_zfs_acl_commands("tank/shared")
    assert any("chmod 775" in cmd for cmd in acl_commands)


def test_permissions_applied_in_mock_mode():
    """Test that permission application is logged in mock mode."""
    perm_mgr = PermissionManager(mock=True)
    zfs_mgr = ZFSManager(mock=True, permission_manager=perm_mgr)
    
    # Register and create
    perm_mgr.register_dataset("tank/test")
    perm_mgr.add_consumer("tank/test", ConsumerType.CONTAINER, "testapp", AccessLevel.WRITE)
    
    # Should succeed in mock mode
    success = zfs_mgr.create_dataset("tank/test", {})
    assert success
    
    # Permissions should be configured
    acl_commands = perm_mgr.get_zfs_acl_commands("tank/test")
    assert len(acl_commands) > 0
