"""Tests for tg status command."""
import subprocess
from pathlib import Path
from typer.testing import CliRunner

from tengil.cli import app

runner = CliRunner()


def test_status_no_git_repo(tmp_path, monkeypatch):
    """Status command warns when directory has no git repo."""
    monkeypatch.setenv('TG_MOCK', '1')

    result = runner.invoke(app, ['status', '--path', str(tmp_path)])

    assert result.exit_code == 1
    assert "No git repository found" in result.stdout


def test_status_directory_not_exist(monkeypatch):
    """Status command fails when directory doesn't exist."""
    monkeypatch.setenv('TG_MOCK', '1')

    result = runner.invoke(app, ['status', '--path', '/nonexistent/path'])

    assert result.exit_code == 1
    assert "does not exist" in result.stdout


def test_status_clean_working_tree(tmp_path, monkeypatch):
    """Status command shows success when working tree is clean."""
    monkeypatch.setenv('TG_MOCK', '1')

    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)

    # Create and commit a file
    config = tmp_path / 'tengil.yml'
    config.write_text('pools: {}')
    subprocess.run(['git', 'add', 'tengil.yml'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=tmp_path, check=True, capture_output=True)

    result = runner.invoke(app, ['status', '--path', str(tmp_path)])

    assert result.exit_code == 0
    assert "Working tree clean" in result.stdout


def test_status_uncommitted_changes(tmp_path, monkeypatch):
    """Status command warns about uncommitted changes."""
    monkeypatch.setenv('TG_MOCK', '1')

    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)

    # Create and commit a file
    config = tmp_path / 'tengil.yml'
    config.write_text('pools: {}')
    subprocess.run(['git', 'add', 'tengil.yml'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=tmp_path, check=True, capture_output=True)

    # Modify the file (uncommitted change)
    config.write_text('pools:\n  tank: {}')

    result = runner.invoke(app, ['status', '--path', str(tmp_path)])

    assert result.exit_code == 0
    assert "modified:" in result.stdout or "tengil.yml" in result.stdout
    assert "commit changes before running 'tg apply'" in result.stdout


def test_status_porcelain_mode(tmp_path, monkeypatch):
    """Status command supports --porcelain for script-friendly output."""
    monkeypatch.setenv('TG_MOCK', '1')

    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)

    # Create and commit a file
    config = tmp_path / 'tengil.yml'
    config.write_text('pools: {}')
    subprocess.run(['git', 'add', 'tengil.yml'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=tmp_path, check=True, capture_output=True)

    # Modify the file
    config.write_text('pools:\n  tank: {}')

    result = runner.invoke(app, ['status', '--path', str(tmp_path), '--porcelain'])

    assert result.exit_code == 0
    # Porcelain mode should show short status
    assert " M tengil.yml" in result.stdout


def test_repo_status_via_repo_subcommand(tmp_path, monkeypatch):
    """Status can also be invoked via 'tg repo status'."""
    monkeypatch.setenv('TG_MOCK', '1')

    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)

    # Create and commit a file
    config = tmp_path / 'tengil.yml'
    config.write_text('pools: {}')
    subprocess.run(['git', 'add', 'tengil.yml'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=tmp_path, check=True, capture_output=True)

    result = runner.invoke(app, ['repo', 'status', '--path', str(tmp_path)])

    assert result.exit_code == 0
    assert "Working tree clean" in result.stdout
