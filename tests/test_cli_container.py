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


def test_container_start_by_name(monkeypatch):
    """Start container resolved by name."""
    monkeypatch.setenv('TG_MOCK', '1')
    captured = {}

    def fake_start(self, vmid):
        captured['vmid'] = vmid
        return True

    monkeypatch.setattr(ContainerLifecycle, 'start_container', fake_start)

    result = runner.invoke(app, ['container', 'start', 'jellyfin'])

    assert result.exit_code == 0
    assert captured['vmid'] == 100  # mock discovery returns jellyfin with VMID 100
    assert 'Started' in result.stdout
    monkeypatch.delenv('TG_MOCK', raising=False)


def test_container_start_failure(monkeypatch):
    """Handle failed container start."""
    monkeypatch.setenv('TG_MOCK', '1')

    def fake_start(self, vmid):
        return False

    monkeypatch.setattr(ContainerLifecycle, 'start_container', fake_start)

    result = runner.invoke(app, ['container', 'start', 'jellyfin'])

    assert result.exit_code == 1
    assert 'Failed to start' in result.stdout
    monkeypatch.delenv('TG_MOCK', raising=False)


def test_container_stop_by_vmid(monkeypatch):
    """Stop container resolved by VMID."""
    monkeypatch.setenv('TG_MOCK', '1')
    captured = {}

    def fake_stop(self, vmid):
        captured['vmid'] = vmid
        return True

    monkeypatch.setattr(ContainerLifecycle, 'stop_container', fake_stop)

    result = runner.invoke(app, ['container', 'stop', '101'])

    assert result.exit_code == 0
    assert captured['vmid'] == 101
    assert 'Stopped' in result.stdout
    monkeypatch.delenv('TG_MOCK', raising=False)


def test_container_stop_by_name(monkeypatch):
    """Stop container by name."""
    monkeypatch.setenv('TG_MOCK', '1')
    captured = {}

    def fake_stop(self, vmid):
        captured['vmid'] = vmid
        return True

    monkeypatch.setattr(ContainerLifecycle, 'stop_container', fake_stop)

    result = runner.invoke(app, ['container', 'stop', 'jellyfin'])

    assert result.exit_code == 0
    assert captured['vmid'] == 100
    assert 'Stopped' in result.stdout
    monkeypatch.delenv('TG_MOCK', raising=False)


def test_container_restart_by_name(monkeypatch):
    """Restart container resolved by name."""
    monkeypatch.setenv('TG_MOCK', '1')
    captured = {}

    def fake_restart(self, vmid):
        captured['vmid'] = vmid
        return True

    monkeypatch.setattr(ContainerLifecycle, 'restart_container', fake_restart)

    result = runner.invoke(app, ['container', 'restart', 'jellyfin'])

    assert result.exit_code == 0
    assert captured['vmid'] == 100
    assert 'Restarted' in result.stdout
    monkeypatch.delenv('TG_MOCK', raising=False)


def test_container_restart_failure(monkeypatch):
    """Handle failed container restart."""
    monkeypatch.setenv('TG_MOCK', '1')

    def fake_restart(self, vmid):
        return False

    monkeypatch.setattr(ContainerLifecycle, 'restart_container', fake_restart)

    result = runner.invoke(app, ['container', 'restart', 'jellyfin'])

    assert result.exit_code == 1
    assert 'Failed to restart' in result.stdout
    monkeypatch.delenv('TG_MOCK', raising=False)
