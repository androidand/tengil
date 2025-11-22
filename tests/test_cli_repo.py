"""Tests for tg repo helper commands."""
from pathlib import Path
from types import SimpleNamespace

import pytest

typer = pytest.importorskip("typer")
from typer.testing import CliRunner  # type: ignore

from tengil.cli import app

runner = CliRunner()


def test_repo_init_creates_gitignore(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, cwd=None, capture_output=False, check=False, text=False):
        calls.append((tuple(args), cwd))
        if args[:2] == ("git", "init") and cwd:
            (Path(cwd) / ".git").mkdir(exist_ok=True)
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr("tengil.cli_setup_commands.subprocess.run", fake_run)

    result = runner.invoke(app, ["repo", "init", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output

    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text()
    assert ".tengil/" in content
    assert "compose_cache/" in content
    assert any(cmd[0][:2] == ("git", "init") for cmd in calls)


def test_repo_status_shows_output(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    def fake_run(args, cwd=None, capture_output=False, check=False, text=False):
        assert args[0:2] == ["git", "status"]
        return SimpleNamespace(stdout=" M tengil.yml\n", stderr="")

    monkeypatch.setattr("tengil.cli_setup_commands.subprocess.run", fake_run)

    result = runner.invoke(app, ["repo", "status", "--path", str(repo_dir)])
    assert result.exit_code == 0, result.output
    assert "tengil.yml" in result.output
