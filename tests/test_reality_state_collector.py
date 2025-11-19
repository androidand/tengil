"""Tests for the RealityStateCollector."""

import pytest

from tengil.services.proxmox.state_collector import RealityStateCollector


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch):
    """Ensure TG_MOCK is enabled for collectors created in tests."""
    monkeypatch.setenv("TG_MOCK", "1")
    yield
    monkeypatch.delenv("TG_MOCK", raising=False)


def test_collects_mock_containers_and_storage():
    collector = RealityStateCollector(mock=True)
    state = collector.collect()

    assert state["metadata"]["mock"] is True
    assert state["metadata"]["container_count"] == 2
    assert len(state["containers"]) == 2

    first = state["containers"][0]
    assert first["vmid"] == 100
    assert first["name"] == "jellyfin"
    assert first["rootfs"]["volume"] == "local-lvm:vm-100-disk-0"
    assert first["mounts"]
    assert first["mounts"][0]["mp"] == "/media"

    storage = state["storage"]
    assert "local-zfs" in storage
    assert state["zfs"]["datasets"]  # May be empty dicts but key should exist


def test_parses_enhanced_container_config():
    class DummyProxmox:
        mock = True

        def list_containers(self):
            return [{"vmid": 200, "name": "svc", "status": "running"}]

        def get_container_config(self, vmid: int):
            return {
                "hostname": "svc",
                "rootfs": "tank/subvol-200-disk-0,size=16G,acl=1",
                "memory": "2048",
                "swap": "512",
                "cores": "4",
                "cpuunits": "1024",
                "cpulimit": "1.5",
                "unprivileged": "1",
                "features": "nesting=1,keyctl=1",
                "net0": "name=eth0,bridge=vmbr0,tag=20,firewall=1,ip=dhcp",
                "mp0": "/tank/data,mp=/data,ro=1",
            }

        def get_container_mounts(self, vmid: int):
            return {}

        def parse_storage_cfg(self):
            return {}

    class DummyZfs:
        mock = True

        def list_datasets(self, pool: str):
            assert pool == "tank"
            return {
                "tank/data": {
                    "used": "1024",
                    "available": "2048",
                    "mountpoint": "/tank/data",
                }
            }

    collector = RealityStateCollector(
        proxmox_manager=DummyProxmox(),
        zfs_manager=DummyZfs(),
    )

    state = collector.collect(pools=["tank"])
    container = state["containers"][0]

    assert container["resources"]["memory_mb"] == 2048
    assert container["resources"]["cores"] == 4
    assert container["resources"]["cpu_units"] == 1024
    assert container["resources"]["cpu_limit"] == pytest.approx(1.5)

    assert container["rootfs"]["volume"] == "tank/subvol-200-disk-0"
    assert container["rootfs"]["size"] == "16G"

    assert container["mounts"][0]["readonly"] is True
    assert container["mounts"][0]["volume"] == "/tank/data"

    network = container["network"][0]
    assert network["id"] == "net0"
    assert network["firewall"] is True
    assert network["tag"] == 20

    features = container["features"]
    assert features["nesting"] is True
    assert features["keyctl"] is True

    datasets = state["zfs"]["datasets"]
    assert "tank" in datasets
    assert "tank/data" in datasets["tank"]
