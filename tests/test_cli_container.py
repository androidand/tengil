"""Tests for container CLI helpers."""

import textwrap
from typer.testing import CliRunner

from tengil.cli import app
from tengil.services.proxmox.containers.lifecycle import ContainerLifecycle

runner = CliRunner()


def test_container_exec_by_name(monkeypatch):
    """Execute command inside container resolved by name."""
    monkeypatch.setenv('TG_MOCK', '1')
    captured = {}

    def fake_exec(self, vmid, command, user=None, env=None, workdir=None):
        captured['vmid'] = vmid
        captured['command'] = command
        captured['user'] = user
        captured['env'] = env
        captured['workdir'] = workdir
        return 0

    monkeypatch.setattr(ContainerLifecycle, 'exec_container_command', fake_exec)

    result = runner.invoke(app, ['container', 'exec', 'jellyfin', '--', 'echo', 'hello'])

    assert result.exit_code == 0
    assert captured['vmid'] == 100  # mock discovery returns jellyfin with VMID 100
    assert captured['command'] == ['echo', 'hello']
    assert captured['user'] is None
    assert captured['workdir'] is None
    assert captured['env'] == {}
    monkeypatch.delenv('TG_MOCK', raising=False)


def test_container_exec_dataset_resolution(monkeypatch, tmp_path):
    """Resolve container via pool/dataset syntax and execute command."""
    monkeypatch.setenv('TG_MOCK', '1')
    config_path = tmp_path / 'tengil.yml'
    config_path.write_text(
        textwrap.dedent("""\
            pools:
                tank:
                    type: zfs
                    datasets:
                        media:
                            profile: media
                            containers:
                                - name: jellyfin
                                  vmid: 120
                                  mount: /media
            """).strip()
    )

    captured = {}

    def fake_exec(self, vmid, command, user=None, env=None, workdir=None):
        captured['vmid'] = vmid
        captured['command'] = command
        return 0

    monkeypatch.setattr(ContainerLifecycle, 'exec_container_command', fake_exec)

    result = runner.invoke(
        app,
        [
            'container', 'exec', 'tank/media:jellyfin',
            '--config', str(config_path), '--', 'echo', 'hi'
        ],
    )

    assert result.exit_code == 0
    assert captured['vmid'] == 120
    assert captured['command'] == ['echo', 'hi']
    monkeypatch.delenv('TG_MOCK', raising=False)


def test_container_shell_by_vmid(monkeypatch):
    """Open shell via VMID resolution."""
    monkeypatch.setenv('TG_MOCK', '1')
    captured = {}

    def fake_shell(self, vmid, user=None):
        captured['vmid'] = vmid
        captured['user'] = user
        return 0

    monkeypatch.setattr(ContainerLifecycle, 'enter_container_shell', fake_shell)

    result = runner.invoke(app, ['container', 'shell', '101', '--user', 'root'])

    assert result.exit_code == 0
    assert captured['vmid'] == 101
    assert captured['user'] == 'root'
    monkeypatch.delenv('TG_MOCK', raising=False)
