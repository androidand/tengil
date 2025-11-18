"""Tests for app CLI repository sync."""

from typer.testing import CliRunner

from tengil.cli import app
from tengil.services.git_manager import GitManager

runner = CliRunner()


def test_app_sync_clone_new_repo(monkeypatch):
    """Clone repository when path is missing."""
    monkeypatch.setenv('TG_MOCK', '1')
    captured = {}
    directories = []

    monkeypatch.setattr(GitManager, 'repo_exists', lambda self, vmid, path: False)

    def fake_ensure(self, vmid, directory):
        directories.append((vmid, directory))
        return True

    def fake_clone(self, vmid, url, destination, branch='main'):
        captured['vmid'] = vmid
        captured['url'] = url
        captured['path'] = destination
        captured['branch'] = branch
        return True

    def fail_pull(self, vmid, destination):
        raise AssertionError('pull_repo should not be called')

    monkeypatch.setattr(GitManager, 'ensure_directory', fake_ensure)
    monkeypatch.setattr(GitManager, 'clone_repo', fake_clone)
    monkeypatch.setattr(GitManager, 'pull_repo', fail_pull)

    result = runner.invoke(
        app,
        [
            'app',
            'sync',
            'jellyfin',
            'https://example.com/myapp.git',
            '--path',
            '/srv/apps/myapp',
            '--branch',
            'develop',
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        'vmid': 100,
        'url': 'https://example.com/myapp.git',
        'path': '/srv/apps/myapp',
        'branch': 'develop',
    }
    assert directories == [(100, '/srv/apps')]
    monkeypatch.delenv('TG_MOCK', raising=False)


def test_app_sync_pull_existing_repo(monkeypatch):
    """Pull repository when .git already exists."""
    monkeypatch.setenv('TG_MOCK', '1')
    pulls = []

    monkeypatch.setattr(GitManager, 'repo_exists', lambda self, vmid, path: True)

    def fake_pull(self, vmid, destination):
        pulls.append((vmid, destination))
        return True

    def fail_clone(self, vmid, url, destination, branch='main'):
        raise AssertionError('clone_repo should not be called')

    monkeypatch.setattr(GitManager, 'pull_repo', fake_pull)
    monkeypatch.setattr(GitManager, 'clone_repo', fail_clone)

    result = runner.invoke(
        app,
        [
            'app',
            'sync',
            'jellyfin',
            'https://example.com/myapp.git',
            '--path',
            '/srv/apps/myapp',
        ],
    )

    assert result.exit_code == 0
    assert pulls == [(100, '/srv/apps/myapp')]
    monkeypatch.delenv('TG_MOCK', raising=False)


def test_app_sync_uses_default_path(monkeypatch):
    """Default destination uses repo name."""
    monkeypatch.setenv('TG_MOCK', '1')
    captured = {}

    monkeypatch.setattr(GitManager, 'repo_exists', lambda self, vmid, path: False)

    def fake_clone(self, vmid, url, destination, branch='main'):
        captured['vmid'] = vmid
        captured['path'] = destination
        captured['branch'] = branch
        return True

    monkeypatch.setattr(GitManager, 'clone_repo', fake_clone)

    result = runner.invoke(
        app,
        [
            'app',
            'sync',
            'jellyfin',
            'https://github.com/example/app-config.git',
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        'vmid': 100,
        'path': '/srv/apps/app-config',
        'branch': 'main',
    }
    monkeypatch.delenv('TG_MOCK', raising=False)


def test_app_sync_with_spec(monkeypatch, tmp_path):
    """Load sync parameters from spec file."""
    monkeypatch.setenv('TG_MOCK', '1')

    spec_path = tmp_path / 'repo-spec.yml'
    spec_path.write_text(
        """
target: jellyfin
repo: https://example.com/spec-app.git
branch: feature/spec
path: /srv/apps/spec-app
""".strip()
    )

    captured = {}
    directories = []

    monkeypatch.setattr(GitManager, 'repo_exists', lambda self, vmid, path: False)

    def fake_ensure(self, vmid, directory):
        directories.append((vmid, directory))
        return True

    def fake_clone(self, vmid, url, destination, branch='main'):
        captured['vmid'] = vmid
        captured['url'] = url
        captured['path'] = destination
        captured['branch'] = branch
        return True

    def fail_pull(*_args, **_kwargs):
        raise AssertionError('pull_repo should not be called')

    monkeypatch.setattr(GitManager, 'ensure_directory', fake_ensure)
    monkeypatch.setattr(GitManager, 'clone_repo', fake_clone)
    monkeypatch.setattr(GitManager, 'pull_repo', fail_pull)

    result = runner.invoke(
        app,
        [
            'app',
            'sync',
            '--spec',
            str(spec_path),
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        'vmid': 100,
        'url': 'https://example.com/spec-app.git',
        'path': '/srv/apps/spec-app',
        'branch': 'feature/spec',
    }
    assert directories == [(100, '/srv/apps')]
    monkeypatch.delenv('TG_MOCK', raising=False)


def test_app_list_with_spec(monkeypatch, tmp_path):
    """List manifests using spec defaults."""
    monkeypatch.setenv('TG_MOCK', '1')

    spec_path = tmp_path / 'repo-spec.yml'
    spec_path.write_text(
        """
target: jellyfin
repo: https://example.com/spec-app.git
path: /srv/apps/spec-app
manifests:
  root: /srv/apps/spec-app/manifests
  glob: "*.app.yml"
  depth: 4
""".strip()
    )

    manifest_paths = [
        '/srv/apps/spec-app/manifests/media/app.app.yml',
        '/srv/apps/spec-app/manifests/system/sys.app.yml',
    ]

    def fake_list(self, vmid, root, pattern, depth):
        assert vmid == 100
        assert root == '/srv/apps/spec-app/manifests'
        assert pattern == '*.app.yml'
        assert depth == 4
        return manifest_paths

    monkeypatch.setattr(GitManager, 'list_manifests', fake_list)

    def fake_read(self, vmid, path):
        if path == manifest_paths[0]:
            return """
name: media-app
version: 1.2.3
description: Media stack manifest
""".strip()
        if path == manifest_paths[1]:
            return """
name: system-app
description: System manifest
""".strip()
        return ""

    monkeypatch.setattr(GitManager, 'read_file', fake_read)

    result = runner.invoke(
        app,
        [
            'app',
            'list',
            '--spec',
            str(spec_path),
        ],
    )

    assert result.exit_code == 0
    assert '2 manifest(s) found' in result.stdout
    assert 'media/app.app.yml' in result.stdout
    assert 'system/sys.app.yml' in result.stdout
    assert 'media-app (1.2.3)' in result.stdout
    assert 'System manifest' in result.stdout
    monkeypatch.delenv('TG_MOCK', raising=False)
