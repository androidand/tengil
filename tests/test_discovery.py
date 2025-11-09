"""Test system discovery and recommendations."""
import pytest
from tengil.discovery import SystemDiscovery, PoolRecommender
from tengil.models.disk import DiskType
from tengil.models.pool import PoolPurpose


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
