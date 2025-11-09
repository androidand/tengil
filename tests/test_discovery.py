"""Test system discovery and recommendations."""
import pytest
from tengil.discovery import SystemDiscovery, PoolRecommender
from tengil.models.disk import DiskType
from tengil.models.pool import PoolPurpose
from tengil.services.proxmox.manager import ProxmoxManager


def test_mock_disk_discovery():
    """Test mock disk discovery."""
    discovery = SystemDiscovery(mock=True)
    disks = discovery.discover_disks()
    
    assert len(disks) == 3
    
    # Check NVMe disk
    nvme = [d for d in disks if d.disk_type == DiskType.NVME][0]
    assert nvme.device == "/dev/nvme0n1"
    assert nvme.is_fast is True
    assert "3.6TB" in nvme.size_human or "4TB" in nvme.size_human  # 4TB = 3.6TiB
    
    # Check HDDs
    hdds = [d for d in disks if d.disk_type == DiskType.HDD]
    assert len(hdds) == 2
    assert all(d.rotational for d in hdds)


def test_mock_pool_discovery():
    """Test mock pool discovery."""
    discovery = SystemDiscovery(mock=True)
    pools = discovery.discover_pools()
    
    assert len(pools) == 2
    
    # Check rpool
    rpool = [p for p in pools if p.name == "rpool"][0]
    assert rpool.pool_type == "single"
    assert len(rpool.devices) == 1
    
    # Check tank
    tank = [p for p in pools if p.name == "tank"][0]
    assert tank.pool_type == "mirror"
    assert len(tank.devices) == 2


def test_pool_recommendations():
    """Test pool recommendation engine."""
    discovery = SystemDiscovery(mock=True)
    disks = discovery.discover_disks()
    pools = discovery.discover_pools()
    
    recommender = PoolRecommender(disks, pools)
    recommendations = recommender.recommend_structure(
        use_cases=['media-server', 'databases']
    )
    
    assert 'pools' in recommendations
    assert 'rpool' in recommendations['pools']
    assert 'tank' in recommendations['pools']
    
    # rpool should have tengil namespace
    rpool_datasets = recommendations['pools']['rpool']
    assert any('tengil' in k for k in rpool_datasets.keys())
    assert any('appdata' in k for k in rpool_datasets.keys())
    assert any('databases' in k for k in rpool_datasets.keys())
    
    # tank should have media structure
    tank_datasets = recommendations['pools']['tank']
    assert 'media/tv' in tank_datasets
    assert 'media/movies' in tank_datasets
    assert 'backups' in tank_datasets


def test_fast_pool_identification():
    """Test identifying fast vs bulk pools."""
    discovery = SystemDiscovery(mock=True)
    pools = discovery.discover_pools()
    
    recommender = PoolRecommender([], pools)
    
    fast_pool = recommender._find_fast_pool()
    assert fast_pool.name == "rpool"
    
    bulk_pool = recommender._find_bulk_pool()
    assert bulk_pool.name == "tank"


def test_os_pool_uses_tengil_namespace():
    """Test that OS pools get tengil namespace recommendations."""
    discovery = SystemDiscovery(mock=True)
    pools = discovery.discover_pools()
    
    recommender = PoolRecommender([], pools)
    recommendations = recommender.recommend_structure(use_cases=['media-server'])
    
    rpool_datasets = recommendations['pools']['rpool']
    
    # All datasets should be under tengil/*
    for dataset_name in rpool_datasets.keys():
        assert dataset_name.startswith('tengil/'), \
            f"Expected tengil namespace but got: {dataset_name}"


def test_recommendations_without_use_cases():
    """Test that recommendations work without specifying use cases."""
    discovery = SystemDiscovery(mock=True)
    disks = discovery.discover_disks()
    pools = discovery.discover_pools()
    
    recommender = PoolRecommender(disks, pools)
    recommendations = recommender.recommend_structure()  # No use_cases
    
    # Should still generate basic structure
    assert 'pools' in recommendations
    assert len(recommendations['pools']) > 0


class TestContainerStateDetection:
    """Test container state detection functionality."""

    def test_list_containers_mock(self):
        """Test listing containers in mock mode."""
        pm = ProxmoxManager(mock=True)
        containers = pm.list_containers()
        
        assert len(containers) == 2
        assert containers[0]['vmid'] == 100
        assert containers[0]['name'] == 'jellyfin'
        assert containers[0]['status'] == 'running'
        
        assert containers[1]['vmid'] == 101
        assert containers[1]['name'] == 'nextcloud'
        assert containers[1]['status'] == 'stopped'

    def test_find_container_by_name(self):
        """Test finding container by name."""
        pm = ProxmoxManager(mock=True)
        
        vmid = pm.find_container_by_name('jellyfin')
        assert vmid == 100
        
        vmid = pm.find_container_by_name('nextcloud')
        assert vmid == 101
        
        vmid = pm.find_container_by_name('nonexistent')
        assert vmid is None

    def test_get_container_info(self):
        """Test getting detailed container info."""
        pm = ProxmoxManager(mock=True)
        
        info = pm.get_container_info(100)
        assert info is not None
        assert info['vmid'] == 100
        assert info['name'] == 'jellyfin'  # Should match list_containers mock data
        assert info['status'] == 'running'
        assert info['template'] == 'debian-12-standard'
        assert info['memory'] == 2048
        assert info['cores'] == 2

    def test_get_container_by_name(self):
        """Test getting container info by name."""
        pm = ProxmoxManager(mock=True)
        
        info = pm.get_container_by_name('jellyfin')
        assert info is not None
        assert info['vmid'] == 100
        assert info['status'] == 'running'
        
        info = pm.get_container_by_name('nonexistent')
        assert info is None

    def test_get_all_containers_info(self):
        """Test getting info for all containers."""
        pm = ProxmoxManager(mock=True)
        
        all_containers = pm.get_all_containers_info()
        assert len(all_containers) == 2
        
        # Check first container
        assert all_containers[0]['vmid'] == 100
        assert all_containers[0]['status'] == 'running'
        
        # Check second container
        assert all_containers[1]['vmid'] == 101
        assert all_containers[1]['status'] == 'stopped'

    def test_container_exists(self):
        """Test checking if container exists."""
        pm = ProxmoxManager(mock=True)
        
        # In mock mode, containers always exist
        assert pm.container_exists(100) is True
        assert pm.container_exists(999) is True

    def test_container_has_mount(self):
        """Test checking if container has specific mount."""
        pm = ProxmoxManager(mock=True)
        
        # In mock mode, no mounts exist
        has_mount = pm.container_has_mount(100, '/tank/media')
        assert has_mount is False

    def test_get_container_mounts(self):
        """Test getting container mount points."""
        pm = ProxmoxManager(mock=True)
        
        mounts = pm.get_container_mounts(100)
        assert isinstance(mounts, dict)
        # Mock returns empty mounts
        assert len(mounts) == 0


class TestContainerInfoStructure:
    """Test the structure of container information."""

    def test_container_info_has_required_fields(self):
        """Container info should have all required fields."""
        pm = ProxmoxManager(mock=True)
        info = pm.get_container_info(100)
        
        required_fields = ['vmid', 'name', 'status', 'template', 
                          'memory', 'cores', 'rootfs', 'mounts']
        
        for field in required_fields:
            assert field in info, f"Missing required field: {field}"

    def test_container_info_types(self):
        """Container info fields should have correct types."""
        pm = ProxmoxManager(mock=True)
        info = pm.get_container_info(100)
        
        assert isinstance(info['vmid'], int)
        assert isinstance(info['name'], str)
        assert isinstance(info['status'], str)
        assert isinstance(info['template'], str)
        assert isinstance(info['memory'], int)
        assert isinstance(info['cores'], int)
        assert isinstance(info['rootfs'], str)
        assert isinstance(info['mounts'], dict)

    def test_all_containers_returns_list_of_dicts(self):
        """get_all_containers_info should return list of dicts."""
        pm = ProxmoxManager(mock=True)
        all_containers = pm.get_all_containers_info()
        
        assert isinstance(all_containers, list)
        assert len(all_containers) > 0
        
        for container in all_containers:
            assert isinstance(container, dict)
            assert 'vmid' in container
            assert 'name' in container
            assert 'status' in container
