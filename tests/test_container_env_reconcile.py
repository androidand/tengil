import subprocess
from types import SimpleNamespace

import pytest

from tengil.services.proxmox.backends.lxc import LXCBackend
from tengil.services.proxmox.backends.oci import OCIBackend
from tengil.services.proxmox.containers.orchestrator import ContainerOrchestrator


def test_lxc_update_env_runs_pct_set(monkeypatch):
    calls = []

    def fake_run(cmd, capture_output=True, text=True, check=True):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend = LXCBackend(mock=False)

    assert backend.update_env(123, {"A": "B", "C": "D"}) is True
    assert calls
    assert calls[0][:4] == ["pct", "set", "123", "--env"]
    assert "--env" in calls[0]


def test_oci_update_env_runs_pct_set(monkeypatch):
    calls = []

    def fake_run(cmd, capture_output=True, text=True, check=True):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend = OCIBackend(mock=False)

    assert backend.update_env(321, {"FOO": "bar"}) is True
    assert calls
    assert calls[0][:4] == ["pct", "set", "321", "--env"]


def test_orchestrator_apply_env_existing_container(monkeypatch):
    updates = SimpleNamespace(oci=False, lxc=False, restarted=False)

    orch = ContainerOrchestrator(mock=True)
    orch.discovery.get_container_info = lambda vmid: {"status": "running", "name": "ct-test"}
    orch.oci_backend.update_env = lambda vmid, env: updates.__setattr__("oci", True) or True
    orch.lxc_backend.update_env = lambda vmid, env: updates.__setattr__("lxc", True) or True
    orch.lifecycle.restart_container = lambda vmid: updates.__setattr__("restarted", True) or True

    oci_spec = {"type": "oci", "env": {"KEY": "VAL"}}
    lxc_spec = {"type": "lxc", "env": {"KEY": "VAL"}}

    assert orch._apply_env(100, oci_spec, "ct-oci") is True
    assert updates.oci is True and updates.restarted is True

    updates.restarted = False
    updates.oci = False
    assert orch._apply_env(200, lxc_spec, "ct-lxc") is True
    assert updates.lxc is True and updates.restarted is True
