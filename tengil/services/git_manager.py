"""Git repository management for app deployment."""
import subprocess
from typing import Optional

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class GitManager:
    """Manages git operations for app deployment."""

    def __init__(self, mock: bool = False):
        self.mock = mock

    def ensure_directory(self, vmid: int, directory: str) -> bool:
        """Ensure a directory exists inside the container."""
        if not directory or directory in {'.', '/'}:
            return True

        if self.mock:
            logger.info(f"MOCK: Would ensure directory {directory} exists in container {vmid}")
            return True

        safe_directory = directory.replace("'", "'\\''")
        cmd = [
            'pct', 'exec', str(vmid), '--',
            'bash', '-c',
            f"mkdir -p '{safe_directory}'"
        ]

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to ensure directory {directory} in container {vmid}: {e}")
            if e.stderr:
                logger.error(f"Error output: {e.stderr}")
            return False

    def repo_exists(self, vmid: int, path: str) -> bool:
        """Check if a git repository already exists at the given path."""
        if self.mock:
            logger.info(f"MOCK: Would check for git repo at {path} in container {vmid}")
            return False

        safe_path = path.replace("'", "'\\''")
        cmd = [
            'pct', 'exec', str(vmid), '--',
            'bash', '-c',
            f"test -d '{safe_path}/.git'"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return True
            return False
        except subprocess.CalledProcessError:
            return False
        except Exception as exc:
            logger.error(f"Failed to check repository existence: {exc}")
            return False

    def read_file(self, vmid: int, path: str) -> Optional[str]:
        """Read a file inside the container and return its contents."""
        if self.mock:
            logger.info(f"MOCK: Would read file {path} in container {vmid}")
            return ""

        safe_path = path.replace("'", "'\\''")
        cmd = [
            'pct', 'exec', str(vmid), '--',
            'bash', '-c',
            f"cat '{safe_path}'"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to read file {path} in container {vmid}: {exc}")
            if exc.stderr:
                logger.error(f"Error output: {exc.stderr}")
            return None

    def list_manifests(
        self,
        vmid: int,
        root: str,
        pattern: str = "*.yml",
        max_depth: int = 3,
    ) -> list[str]:
        """List manifest files under a directory inside the container."""
        if max_depth < 1:
            max_depth = 1

        if self.mock:
            logger.info(
                "MOCK: Would list manifests in container %s under %s (pattern %s, depth %s)",
                vmid,
                root,
                pattern,
                max_depth,
            )
            return []

        safe_root = root.replace("'", "'\\''")
        safe_pattern = pattern.replace("'", "'\\''")

        cmd = [
            'pct', 'exec', str(vmid), '--',
            'bash', '-c',
            (
                "if [ -d '{root}' ]; then "
                "find '{root}' -maxdepth {depth} -type f -name '{pattern}' -print; "
                "fi"
            ).format(root=safe_root, depth=max_depth, pattern=safe_pattern)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.error(
                "Failed to list manifests in %s (vmid %s): %s",
                root,
                vmid,
                exc,
            )
            if exc.stderr:
                logger.error("Error output: %s", exc.stderr)
            return []

        paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return paths

    def clone_repo(
        self,
        vmid: int,
        url: str,
        path: str,
        branch: str = "main"
    ) -> bool:
        """Clone a git repository into a container.

        Args:
            vmid: Container ID
            url: Git repository URL
            path: Path inside container to clone to
            branch: Branch to clone (default: main)

        Returns:
            True if successful, False otherwise
        """
        if self.mock:
            logger.info(f"MOCK: Would clone {url} ({branch}) to container {vmid}:{path}")
            return True

        # Escape single quotes for shell safety
        safe_url = url.replace("'", "'\\''")
        safe_path = path.replace("'", "'\\''")
        safe_branch = branch.replace("'", "'\\''")

        # First, ensure git is installed
        check_git = [
            'pct', 'exec', str(vmid), '--',
            'which', 'git'
        ]

        try:
            result = subprocess.run(
                check_git,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                logger.info(f"Installing git in container {vmid}")
                install_git = [
                    'pct', 'exec', str(vmid), '--',
                    'bash', '-c',
                    'apt-get update && apt-get install -y git'
                ]
                subprocess.run(install_git, check=True, capture_output=True, text=True)

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install git in container {vmid}: {e}")
            return False

        # Clone the repository
        clone_cmd = [
            'pct', 'exec', str(vmid), '--',
            'bash', '-c',
            f"git clone -b '{safe_branch}' '{safe_url}' '{safe_path}'"
        ]

        try:
            logger.info(f"Cloning {url} (branch: {branch}) to container {vmid}:{path}")
            result = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"✓ Successfully cloned repository to {path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repository: {e}")
            if e.stderr:
                logger.error(f"Error output: {e.stderr}")
            return False

    def pull_repo(self, vmid: int, path: str) -> bool:
        """Pull latest changes from git repository.

        Args:
            vmid: Container ID
            path: Path to git repository inside container

        Returns:
            True if successful, False otherwise
        """
        if self.mock:
            logger.info(f"MOCK: Would git pull in container {vmid}:{path}")
            return True

        safe_path = path.replace("'", "'\\''")

        pull_cmd = [
            'pct', 'exec', str(vmid), '--',
            'bash', '-c',
            f"cd '{safe_path}' && git pull"
        ]

        try:
            logger.info(f"Pulling latest changes in container {vmid}:{path}")
            result = subprocess.run(
                pull_cmd,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"✓ Successfully pulled latest changes")
            if result.stdout:
                logger.debug(f"Git output: {result.stdout}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to pull repository: {e}")
            if e.stderr:
                logger.error(f"Error output: {e.stderr}")
            return False

    def get_current_commit(self, vmid: int, path: str) -> Optional[str]:
        """Get current commit hash from repository.

        Args:
            vmid: Container ID
            path: Path to git repository inside container

        Returns:
            Commit hash or None if failed
        """
        if self.mock:
            return "mock-commit-hash-1234567890"

        safe_path = path.replace("'", "'\\''")

        cmd = [
            'pct', 'exec', str(vmid), '--',
            'bash', '-c',
            f"cd '{safe_path}' && git rev-parse HEAD"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get commit hash: {e}")
            return None
