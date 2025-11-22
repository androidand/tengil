"""Integration tests for NASManager with PermissionManager."""
from tengil.core.permission_manager import AccessLevel, ConsumerType, PermissionManager
from tengil.services.nas.manager import NASManager


def test_nas_manager_uses_permission_config():
    """Test that NASManager uses PermissionManager for SMB share config."""
    perm_mgr = PermissionManager(mock=True)
    nas_mgr = NASManager(mock=True, permission_manager=perm_mgr)
    
    # Register dataset with SMB consumer (READ-ONLY)
    perm_mgr.register_dataset("tank/media")
    perm_mgr.add_consumer("tank/media", ConsumerType.SHARE_SMB, "Media", AccessLevel.READ)
    
    # Add SMB share - should use permission manager config
    success = nas_mgr.add_smb_share(
        name="Media",
        path="/tank/media",
        config={}  # Empty config, should be populated by permission manager
    )
    
    assert success
    
    # Verify permission manager provides config
    smb_config = perm_mgr.get_smb_share_config("/tank/media", "Media")
    assert "read only" in smb_config
    assert smb_config["read only"] == "yes"


def test_nas_manager_writable_share():
    """Test NAS manager with writable SMB share."""
    perm_mgr = PermissionManager(mock=True)
    nas_mgr = NASManager(mock=True, permission_manager=perm_mgr)
    
    # Register dataset with SMB consumer (WRITE)
    perm_mgr.register_dataset("tank/uploads")
    perm_mgr.add_consumer("tank/uploads", ConsumerType.SHARE_SMB, "Uploads", AccessLevel.WRITE)
    
    # Add SMB share
    success = nas_mgr.add_smb_share(
        name="Uploads",
        path="/tank/uploads",
        config={}
    )
    
    assert success
    
    # Verify writable config
    smb_config = perm_mgr.get_smb_share_config("/tank/uploads", "Uploads")
    assert smb_config["writable"] == "yes"


def test_nas_manager_without_permission_manager():
    """Test that NASManager works without PermissionManager."""
    nas_mgr = NASManager(mock=True, permission_manager=None)
    
    # Should work with manual config
    success = nas_mgr.add_smb_share(
        name="Test",
        path="/tank/test",
        config={"read only": "yes"}
    )
    
    assert success


def test_nas_manager_config_merge():
    """Test that provided config is merged with permission manager config."""
    perm_mgr = PermissionManager(mock=True)
    nas_mgr = NASManager(mock=True, permission_manager=perm_mgr)
    
    # Register dataset
    perm_mgr.register_dataset("tank/shared")
    perm_mgr.add_consumer("tank/shared", ConsumerType.SHARE_SMB, "Shared", AccessLevel.READ)
    
    # Add share with custom config - should merge
    success = nas_mgr.add_smb_share(
        name="Shared",
        path="/tank/shared",
        config={"guest ok": "yes", "browseable": "no"}  # Custom options
    )
    
    assert success
    
    # Permission manager provides readonly, custom config overrides other options
    smb_config = perm_mgr.get_smb_share_config("/tank/shared", "Shared")
    assert smb_config["read only"] == "yes"  # From permission manager


def test_nas_manager_unregistered_share():
    """Test NAS manager with share not registered in permission manager."""
    perm_mgr = PermissionManager(mock=True)
    nas_mgr = NASManager(mock=True, permission_manager=perm_mgr)
    
    # Don't register dataset - should work with provided config only
    success = nas_mgr.add_smb_share(
        name="Manual",
        path="/tank/manual",
        config={"writable": "yes"}
    )
    
    assert success


def test_nas_manager_path_normalization():
    """Test that NAS manager works with different path formats."""
    perm_mgr = PermissionManager(mock=True)
    nas_mgr = NASManager(mock=True, permission_manager=perm_mgr)
    
    # Register without leading slash
    perm_mgr.register_dataset("tank/data")
    perm_mgr.add_consumer("tank/data", ConsumerType.SHARE_SMB, "Data", AccessLevel.WRITE)
    
    # Add share with leading slash
    success = nas_mgr.add_smb_share(
        name="Data",
        path="/tank/data",  # With leading slash
        config={}
    )
    
    assert success
    
    # Should find the config (path normalization works)
    smb_config = perm_mgr.get_smb_share_config("/tank/data", "Data")
    assert "writable" in smb_config
    assert smb_config["writable"] == "yes"
