"""Integration tests for MountManager with PermissionManager."""
from tengil.core.permission_manager import AccessLevel, ConsumerType, PermissionManager
from tengil.services.proxmox.containers.mounts import MountManager


def test_mount_manager_uses_permission_readonly():
    """Test that MountManager respects PermissionManager readonly flag."""
    perm_mgr = PermissionManager(mock=True)
    mount_mgr = MountManager(mock=True, permission_manager=perm_mgr)
    
    # Register dataset with READ-ONLY consumer
    perm_mgr.register_dataset("tank/media")
    perm_mgr.add_consumer("tank/media", ConsumerType.CONTAINER, "jellyfin", AccessLevel.READ)
    
    # Add mount - should be readonly even though we pass readonly=False
    success = mount_mgr.add_container_mount(
        vmid=100,
        mount_point=0,
        host_path="/tank/media",
        container_path="/media",
        readonly=False,  # Try to make writable
        container_name="jellyfin"
    )
    
    assert success  # Should succeed in mock mode
    
    # Verify permission manager says readonly
    flags = perm_mgr.get_container_mount_flags("/tank/media", "jellyfin")
    assert flags["readonly"] is True


def test_mount_manager_uses_permission_readwrite():
    """Test that MountManager respects PermissionManager write flag."""
    perm_mgr = PermissionManager(mock=True)
    mount_mgr = MountManager(mock=True, permission_manager=perm_mgr)
    
    # Register dataset with WRITE consumer
    perm_mgr.register_dataset("tank/data")
    perm_mgr.add_consumer("tank/data", ConsumerType.CONTAINER, "app", AccessLevel.WRITE)
    
    # Add mount - should be writable
    success = mount_mgr.add_container_mount(
        vmid=101,
        mount_point=0,
        host_path="/tank/data",
        container_path="/data",
        readonly=True,  # Try to make readonly
        container_name="app"
    )
    
    assert success
    
    # Verify permission manager says writable
    flags = perm_mgr.get_container_mount_flags("/tank/data", "app")
    assert flags["readonly"] is False


def test_mount_manager_without_permission_manager():
    """Test that MountManager works without PermissionManager."""
    mount_mgr = MountManager(mock=True, permission_manager=None)
    
    # Should use the readonly parameter directly
    success = mount_mgr.add_container_mount(
        vmid=102,
        mount_point=0,
        host_path="/tank/test",
        container_path="/test",
        readonly=True,
        container_name="testapp"
    )
    
    assert success


def test_mount_manager_without_container_name():
    """Test mount without container_name (no permission lookup)."""
    perm_mgr = PermissionManager(mock=True)
    mount_mgr = MountManager(mock=True, permission_manager=perm_mgr)
    
    # Register consumer
    perm_mgr.register_dataset("tank/data")
    perm_mgr.add_consumer("tank/data", ConsumerType.CONTAINER, "app", AccessLevel.READ)
    
    # Add mount without container_name - should use readonly parameter
    success = mount_mgr.add_container_mount(
        vmid=103,
        mount_point=0,
        host_path="/tank/data",
        container_path="/data",
        readonly=False,  # No name, so this will be used
        container_name=None
    )
    
    assert success


def test_mount_manager_unregistered_dataset():
    """Test mount for dataset not registered with permission manager."""
    perm_mgr = PermissionManager(mock=True)
    mount_mgr = MountManager(mock=True, permission_manager=perm_mgr)
    
    # Don't register dataset - should fall back to readonly parameter
    success = mount_mgr.add_container_mount(
        vmid=104,
        mount_point=0,
        host_path="/tank/unregistered",
        container_path="/data",
        readonly=True,
        container_name="app"
    )
    
    assert success


def test_mount_manager_respects_permission_priority():
    """Test that permission manager overrides manual readonly setting."""
    perm_mgr = PermissionManager(mock=True)
    mount_mgr = MountManager(mock=True, permission_manager=perm_mgr)
    
    # Setup: Dataset with WRITE access
    perm_mgr.register_dataset("tank/shared")
    perm_mgr.add_consumer("tank/shared", ConsumerType.CONTAINER, "writer", AccessLevel.WRITE)
    
    # Try to mount as readonly=True, but permission manager should override to writable
    success = mount_mgr.add_container_mount(
        vmid=105,
        mount_point=0,
        host_path="/tank/shared",
        container_path="/shared",
        readonly=True,  # This should be overridden
        container_name="writer"
    )
    
    assert success
    
    # Verify override worked
    flags = perm_mgr.get_container_mount_flags("/tank/shared", "writer")
    assert flags["readonly"] is False
    assert flags["access"] == "write"
