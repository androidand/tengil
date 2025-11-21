"""Integration-style tests for OCIBackend command generation (mocked subprocess)."""
from pathlib import Path
from unittest.mock import patch, MagicMock

from tengil.services.proxmox.backends.oci import OCIBackend


def _completed(stdout=""):
    return MagicMock(returncode=0, stdout=stdout, stderr="")


def test_create_container_with_env_mount_gpu_sequence():
    backend = OCIBackend(mock=False)
    spec = {
        "oci": {"image": "nginx", "tag": "alpine"},
        "vmid": 1000,
        "hostname": "nginx-oci",
        "cores": 1,
        "memory": 512,
        "disk": 8,
        "network": {"ip": "dhcp"},
        "env": {"KEY": "VALUE", "FOO": "BAR"},
        "mounts": [{"source": "/tank/data", "target": "/data", "readonly": True}],
        "gpu": {"passthrough": True},
        "features": {"nesting": 1},
    }

    # Mock to force pull and skip mp detection parsing
    with patch.object(Path, "exists", return_value=False), \
         patch.object(backend, "_get_next_mp_slot", return_value=0), \
         patch("subprocess.run") as mock_run:

        # side effects: skopeo copy, pct create, pct set (mp), pct set (gpu)
        mock_run.side_effect = [
            _completed(),  # skopeo copy
            _completed(),  # pct create
            _completed(),  # pct set mp
            _completed(),  # pct set gpu
        ]

        vmid = backend.create_container(spec, storage="tank")
        assert vmid == 1000

        cmds = [call[0][0] for call in mock_run.call_args_list]
        # First call skopeo copy
        assert cmds[0][0] == "skopeo"
        # Second call pct create with env flags and features/nesting
        create_cmd = cmds[1]
        assert create_cmd[:2] == ["pct", "create"]
        assert "--env" in create_cmd
        # Third call pct set --mp0
        assert cmds[2][:3] == ["pct", "set", "1000"]
        assert any("--mp0" in part for part in cmds[2])
        # Fourth call pct set gpu devices
        assert cmds[3][:3] == ["pct", "set", "1000"]
        assert "/dev/dri/card0" in cmds[3]


def test_create_container_missing_image_returns_none():
    backend = OCIBackend(mock=False)
    spec = {"oci": {"tag": "latest"}}
    with patch("subprocess.run") as mock_run:
        vmid = backend.create_container(spec)
    assert vmid is None
    mock_run.assert_not_called()


def test_pull_failure_returns_none():
    backend = OCIBackend(mock=False)
    spec = {"oci": {"image": "bad/image", "tag": "latest"}}

    with patch.object(Path, "exists", return_value=False), \
         patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr="pull failed")
        ]
        vmid = backend.create_container(spec)
    assert vmid is None


def test_invalid_mount_spec_returns_none():
    """Invalid mount (missing target) should skip create."""
    backend = OCIBackend(mock=False)
    spec = {
        "oci": {"image": "nginx", "tag": "latest"},
        "mounts": [{"source": "/tank/data"}],  # missing target
    }

    with patch("subprocess.run") as mock_run, \
         patch.object(Path, "exists", return_value=False):
        # first call would be skopeo; ensure we abort before pct create
        mock_run.return_value = _completed()
        vmid = backend.create_container(spec)

    assert vmid is None
    # only the pull should have been attempted
    mock_run.assert_called_once()


def test_multi_container_specs_called_individually():
    """Simulate creating multiple OCI specs (e.g., Immich stack)."""
    backend = OCIBackend(mock=False)
    specs = [
        {"oci": {"image": "redis", "tag": "alpine"}, "vmid": 3001},
        {"oci": {"image": "postgres", "tag": "15-alpine"}, "vmid": 3002},
        {"oci": {"image": "ghcr.io/immich-app/immich-server", "tag": "latest"}, "vmid": 3003},
        {"oci": {"image": "ghcr.io/immich-app/immich-machine-learning", "tag": "latest"}, "vmid": 3004},
    ]

    with patch.object(Path, "exists", return_value=False), \
         patch.object(backend, "_get_next_mp_slot", return_value=0), \
         patch("subprocess.run") as mock_run:

        # one skopeo copy + one pct create per spec
        mock_run.side_effect = [_completed(), _completed()] * len(specs)

        for spec in specs:
            vmid = backend.create_container(spec, storage="tank")
            assert vmid == spec["vmid"]

        # ensure we invoked skopeo for each image
        skopeo_calls = [call for call in mock_run.call_args_list if call[0][0][0] == "skopeo"]
        assert len(skopeo_calls) == len(specs)
