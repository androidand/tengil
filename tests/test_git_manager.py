"""Tests for git repository management."""
import subprocess
from unittest.mock import Mock, patch

from tengil.services.git_manager import GitManager


class TestGitManager:
    """Test GitManager operations."""

    def test_clone_repo_mock_mode(self):
        """Test clone in mock mode."""
        manager = GitManager(mock=True)
        result = manager.clone_repo(
            vmid=100,
            url="https://github.com/user/repo",
            path="/app",
            branch="main"
        )
        assert result is True

    @patch('subprocess.run')
    def test_clone_repo_git_already_installed(self, mock_run):
        """Test cloning when git is already installed."""
        manager = GitManager(mock=False)

        # Mock git check (git is installed)
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = manager.clone_repo(
            vmid=100,
            url="https://github.com/user/repo",
            path="/app",
            branch="main"
        )

        assert result is True
        # Should check for git, then clone (2 calls total)
        assert mock_run.call_count == 2

        # First call: check git
        assert mock_run.call_args_list[0][0][0] == [
            'pct', 'exec', '100', '--', 'which', 'git'
        ]

        # Second call: clone
        clone_cmd = mock_run.call_args_list[1][0][0]
        assert clone_cmd[:4] == ['pct', 'exec', '100', '--']
        assert 'git clone' in clone_cmd[-1]
        assert "'main'" in clone_cmd[-1]
        assert "'https://github.com/user/repo'" in clone_cmd[-1]
        assert "'/app'" in clone_cmd[-1]

    @patch('subprocess.run')
    def test_clone_repo_installs_git_if_missing(self, mock_run):
        """Test that git is installed if not present."""
        manager = GitManager(mock=False)

        # Mock git check (git NOT installed), then install, then clone
        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            if 'which' in cmd:
                return Mock(returncode=1)  # git not found
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = run_side_effect

        result = manager.clone_repo(
            vmid=100,
            url="https://github.com/user/repo",
            path="/app"
        )

        assert result is True
        # Should: check git, install git, clone (3 calls)
        assert mock_run.call_count == 3

        # Second call should be git installation
        install_cmd = mock_run.call_args_list[1][0][0]
        assert 'apt-get update' in install_cmd[-1]
        assert 'apt-get install -y git' in install_cmd[-1]

    @patch('subprocess.run')
    def test_clone_repo_with_ssh_url(self, mock_run):
        """Test cloning with SSH URL."""
        manager = GitManager(mock=False)
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = manager.clone_repo(
            vmid=100,
            url="git@github.com:user/repo.git",
            path="/app",
            branch="develop"
        )

        assert result is True
        # Check the clone command has the SSH URL
        clone_cmd = mock_run.call_args_list[1][0][0]
        assert "'git@github.com:user/repo.git'" in clone_cmd[-1]
        assert "'develop'" in clone_cmd[-1]

    @patch('subprocess.run')
    def test_clone_repo_escapes_dangerous_characters(self, mock_run):
        """Test that single quotes are escaped for shell safety."""
        manager = GitManager(mock=False)
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = manager.clone_repo(
            vmid=100,
            url="https://github.com/user/repo's-name",
            path="/app/it's-here",
            branch="feature's-branch"
        )

        assert result is True
        clone_cmd = mock_run.call_args_list[1][0][0][-1]

        # Single quotes should be escaped as '\''
        assert "repo'\\''s-name" in clone_cmd
        assert "it'\\''s-here" in clone_cmd
        assert "feature'\\''s-branch" in clone_cmd

    @patch('subprocess.run')
    def test_clone_repo_handles_git_install_failure(self, mock_run):
        """Test handling of git installation failure."""
        manager = GitManager(mock=False)

        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            if 'which' in cmd:
                return Mock(returncode=1)  # git not found
            if 'apt-get' in cmd[-1]:
                raise subprocess.CalledProcessError(1, cmd, stderr="Package not found")
            return Mock(returncode=0)

        mock_run.side_effect = run_side_effect

        result = manager.clone_repo(
            vmid=100,
            url="https://github.com/user/repo",
            path="/app"
        )

        assert result is False

    @patch('subprocess.run')
    def test_clone_repo_handles_clone_failure(self, mock_run):
        """Test handling of clone failure."""
        manager = GitManager(mock=False)

        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            if 'which' in cmd:
                return Mock(returncode=0)  # git installed
            if 'git clone' in cmd[-1]:
                raise subprocess.CalledProcessError(
                    1, cmd, stderr="fatal: repository not found"
                )
            return Mock(returncode=0)

        mock_run.side_effect = run_side_effect

        result = manager.clone_repo(
            vmid=100,
            url="https://github.com/user/nonexistent",
            path="/app"
        )

        assert result is False

    def test_pull_repo_mock_mode(self):
        """Test pull in mock mode."""
        manager = GitManager(mock=True)
        result = manager.pull_repo(vmid=100, path="/app")
        assert result is True

    @patch('subprocess.run')
    def test_pull_repo_success(self, mock_run):
        """Test pulling latest changes."""
        manager = GitManager(mock=False)
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Already up to date.\n",
            stderr=""
        )

        result = manager.pull_repo(vmid=100, path="/app")

        assert result is True
        mock_run.assert_called_once()

        cmd = mock_run.call_args[0][0]
        assert cmd[:4] == ['pct', 'exec', '100', '--']
        assert "cd '/app'" in cmd[-1]
        assert "git pull" in cmd[-1]

    @patch('subprocess.run')
    def test_pull_repo_escapes_path(self, mock_run):
        """Test that pull escapes single quotes in path."""
        manager = GitManager(mock=False)
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = manager.pull_repo(vmid=100, path="/app/project's-dir")

        assert result is True
        cmd = mock_run.call_args[0][0][-1]
        assert "project'\\''s-dir" in cmd

    @patch('subprocess.run')
    def test_pull_repo_handles_failure(self, mock_run):
        """Test handling of pull failure."""
        manager = GitManager(mock=False)
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ['git', 'pull'], stderr="fatal: not a git repository"
        )

        result = manager.pull_repo(vmid=100, path="/app")

        assert result is False

    def test_get_current_commit_mock_mode(self):
        """Test get commit in mock mode."""
        manager = GitManager(mock=True)
        commit = manager.get_current_commit(vmid=100, path="/app")
        assert commit == "mock-commit-hash-1234567890"

    @patch('subprocess.run')
    def test_get_current_commit_success(self, mock_run):
        """Test getting current commit hash."""
        manager = GitManager(mock=False)
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123def456789\n",
            stderr=""
        )

        commit = manager.get_current_commit(vmid=100, path="/app")

        assert commit == "abc123def456789"
        mock_run.assert_called_once()

        cmd = mock_run.call_args[0][0]
        assert cmd[:4] == ['pct', 'exec', '100', '--']
        assert "cd '/app'" in cmd[-1]
        assert "git rev-parse HEAD" in cmd[-1]

    @patch('subprocess.run')
    def test_get_current_commit_escapes_path(self, mock_run):
        """Test that get_current_commit escapes path."""
        manager = GitManager(mock=False)
        mock_run.return_value = Mock(returncode=0, stdout="abc123\n", stderr="")

        commit = manager.get_current_commit(vmid=100, path="/app's/dir")

        cmd = mock_run.call_args[0][0][-1]
        assert "app'\\''s" in cmd

    @patch('subprocess.run')
    def test_get_current_commit_handles_failure(self, mock_run):
        """Test handling of commit hash retrieval failure."""
        manager = GitManager(mock=False)
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ['git', 'rev-parse'], stderr="fatal: not a git repository"
        )

        commit = manager.get_current_commit(vmid=100, path="/app")

        assert commit is None

    @patch('subprocess.run')
    def test_get_current_commit_strips_whitespace(self, mock_run):
        """Test that commit hash is stripped of whitespace."""
        manager = GitManager(mock=False)
        mock_run.return_value = Mock(
            returncode=0,
            stdout="  abc123def456  \n\n",
            stderr=""
        )

        commit = manager.get_current_commit(vmid=100, path="/app")

        assert commit == "abc123def456"
