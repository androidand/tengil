"""Snapshot tests for CLI help output."""
import pytest
from typer.testing import CliRunner

from tengil.cli import app

runner = CliRunner()


class TestMainHelp:
    """Test main CLI help output."""

    def test_main_help(self):
        """Main help shows core commands and command groups."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        output = result.stdout

        # Check main description
        assert "Tengil - Declarative infrastructure for Proxmox homelabs" in output
        assert "One YAML file. Storage + containers + shares." in output

        # Check quick start guide
        assert "tg packages list" in output
        assert "tg init --package media-server" in output
        assert "tg diff" in output
        assert "tg apply" in output

        # Check core commands are listed
        assert "apply" in output
        assert "diff" in output
        assert "init" in output
        assert "discover" in output

        # Check command groups are listed
        assert "app" in output
        assert "container" in output
        assert "compose" in output


class TestContainerHelp:
    """Test container command group help output."""

    def test_container_help(self):
        """Container group shows all lifecycle commands."""
        result = runner.invoke(app, ["container", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        # Check all container commands
        assert "exec" in output
        assert "shell" in output
        assert "start" in output
        assert "stop" in output
        assert "restart" in output

        # Check help descriptions exist
        assert "Execute" in output or "command" in output
        assert "Interactive" in output or "shell" in output

    def test_container_start_help(self):
        """Container start command has proper help."""
        result = runner.invoke(app, ["container", "start", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        assert "Start a stopped container" in output
        assert "target" in output.lower()
        assert "config" in output.lower()

    def test_container_exec_help(self):
        """Container exec command has proper help."""
        result = runner.invoke(app, ["container", "exec", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        assert "Execute a command" in output
        assert "target" in output.lower()


class TestAppHelp:
    """Test app command group help output."""

    def test_app_help(self):
        """App group shows repository management commands."""
        result = runner.invoke(app, ["app", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        # Check app commands
        assert "sync" in output
        assert "list" in output

    def test_app_sync_help(self):
        """App sync command has proper help."""
        result = runner.invoke(app, ["app", "sync", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        assert "Clone or update" in output or "Git" in output or "repository" in output
        assert "target" in output.lower()
        assert "repo" in output.lower()

    def test_app_list_help(self):
        """App list command has proper help."""
        result = runner.invoke(app, ["app", "list", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        assert "manifest" in output.lower()


class TestComposeHelp:
    """Test compose command group help output."""

    def test_compose_help(self):
        """Compose group shows Docker Compose analysis commands."""
        result = runner.invoke(app, ["compose", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        # Check compose commands exist
        assert "analyze" in output or "validate" in output or "resolve" in output

    def test_compose_analyze_help(self):
        """Compose analyze command has help."""
        result = runner.invoke(app, ["compose", "analyze", "--help"])

        assert result.exit_code == 0
        # Just verify it doesn't crash and has some output
        assert len(result.stdout) > 0


class TestDiscoverHelp:
    """Test discover command group help output."""

    def test_discover_help(self):
        """Discover group shows discovery commands."""
        result = runner.invoke(app, ["discover", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        # Check discover subcommands
        assert "datasets" in output or "containers" in output or "docker" in output

    def test_discover_datasets_help(self):
        """Discover datasets command has help."""
        result = runner.invoke(app, ["discover", "datasets", "--help"])

        assert result.exit_code == 0
        # Just verify it doesn't crash
        assert len(result.stdout) > 0


class TestEnvHelp:
    """Test env command group help output."""

    def test_env_help(self):
        """Env group shows environment variable commands."""
        result = runner.invoke(app, ["env", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        # Check env commands
        assert "list" in output
        assert "set" in output
        assert "sync" in output

    def test_env_list_help(self):
        """Env list command has help."""
        result = runner.invoke(app, ["env", "list", "--help"])

        assert result.exit_code == 0
        assert len(result.stdout) > 0


class TestCoreCommandHelp:
    """Test core infrastructure command help output."""

    def test_diff_help(self):
        """Diff command shows proper help."""
        result = runner.invoke(app, ["diff", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        assert "Show planned changes" in output or "diff" in output.lower()
        assert "config" in output.lower()

    def test_apply_help(self):
        """Apply command shows proper help."""
        result = runner.invoke(app, ["apply", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        assert "Apply" in output or "changes" in output
        assert "yes" in output.lower() or "dry-run" in output.lower()

    def test_init_help(self):
        """Init command shows proper help."""
        result = runner.invoke(app, ["init", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        assert "Initialize" in output or "config" in output
        assert "package" in output.lower() or "template" in output.lower()

    def test_packages_help(self):
        """Packages command shows proper help."""
        result = runner.invoke(app, ["packages", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        assert "package" in output.lower()

    def test_templates_help(self):
        """Templates command shows proper help."""
        result = runner.invoke(app, ["templates", "--help"])

        assert result.exit_code == 0
        output = result.stdout

        assert "template" in output.lower()


class TestHelpStability:
    """Test that help output is stable and doesn't crash."""

    @pytest.mark.parametrize("command", [
        ["--help"],
        ["container", "--help"],
        ["app", "--help"],
        ["compose", "--help"],
        ["discover", "--help"],
        ["env", "--help"],
        ["diff", "--help"],
        ["apply", "--help"],
        ["init", "--help"],
        ["snapshot", "--help"],
        ["rollback", "--help"],
        ["doctor", "--help"],
        ["version", "--help"],
    ])
    def test_help_does_not_crash(self, command):
        """All help commands should exit cleanly."""
        result = runner.invoke(app, command)

        # Help should always succeed
        assert result.exit_code == 0

        # Should produce some output
        assert len(result.stdout) > 0

        # Should not have errors
        assert "Error" not in result.stdout
        assert "Traceback" not in result.stdout
