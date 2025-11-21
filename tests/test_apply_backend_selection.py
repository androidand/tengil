"""Ensure apply pipeline routes OCI specs to OCI backend (mocked)."""
from unittest.mock import patch, MagicMock
from tengil.services.proxmox.containers.orchestrator import ContainerOrchestrator


def test_apply_routes_oci_spec():
    orch = ContainerOrchestrator(mock=True)
    spec = {
        "name": "test-oci",
        "type": "oci",
        "vmid": 150,
        "oci": {"image": "nginx", "tag": "alpine"},
    }

    with patch.object(orch.oci_backend, "pull_image", return_value="local:vztmpl/nginx-alpine.tar") as mock_pull, \
         patch.object(orch.oci_backend, "create_container", return_value=150) as mock_create:
        vmid = orch.create_container(spec, storage="tank")

    assert vmid == 150
    mock_pull.assert_called_once_with("nginx", "alpine", None)
    mock_create.assert_called_once()


def test_apply_routes_lxc_spec():
    orch = ContainerOrchestrator(mock=True)
    spec = {
        "name": "test-lxc",
        "vmid": 151,
        "template": "debian-12-standard",
        "cores": 1,
        "memory": 512,
    }

    with patch.object(orch.lifecycle, "create_container", return_value=151) as mock_lxc:
        vmid = orch.create_container(spec, storage="tank")

    assert vmid == 151
    mock_lxc.assert_called_once()
