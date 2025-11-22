"""Template management for Proxmox LXC containers."""
import subprocess
from typing import List

from tengil.core.logger import get_logger
from tengil.core.retry import retry
from tengil.core.config import get_config

logger = get_logger(__name__)


class TemplateManager:
    """Manages Proxmox LXC templates (download, list, ensure availability)."""

    def __init__(self, mock: bool = False):
        self.mock = mock

    def list_available_templates(self) -> List[str]:
        """Get list of available templates from Proxmox repository.

        Returns:
            List of template names (e.g., ['debian-12-standard', 'ubuntu-22.04-standard'])
        """
        if self.mock:
            return [
                'debian-12-standard',
                'ubuntu-22.04-standard',
                'debian-12-turnkey-mediaserver',
            ]

        # Update template list first
        try:
            subprocess.run(['pveam', 'update'], capture_output=True, check=True)
        except subprocess.CalledProcessError:
            logger.warning("Failed to update template list")

        # Get available templates
        try:
            result = subprocess.run(
                ['pveam', 'available'],
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get available templates: {e}")
            return []

        # Parse output, extract template names
        templates = []
        for line in result.stdout.splitlines():
            if 'vztmpl' in line:
                # Extract template name from line
                parts = line.split()
                if len(parts) > 1:
                    # Template names like "debian-12-standard_12.2-1_amd64.tar.zst"
                    # Extract base name without version/arch suffix
                    template_full = parts[1]
                    # Remove .tar.zst extension
                    template_base = template_full.replace('.tar.zst', '').replace('.tar.xz', '')
                    templates.append(template_base)

        return templates

    def template_exists_locally(self, template: str) -> bool:
        """Check if template is downloaded locally.

        Args:
            template: Template name (e.g., 'debian-12-standard')

        Returns:
            True if template exists locally
        """
        if self.mock:
            # In mock mode, common templates exist
            return template in ['debian-12-standard', 'ubuntu-22.04-standard']

        try:
            result = subprocess.run(
                ['pveam', 'list', 'local'],
                capture_output=True,
                text=True,
                check=True
            )
            return template in result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check local templates: {e}")
            return False

    def resolve_template_filename(self, template: str) -> str:
        """Resolve short template name to full filename.

        Args:
            template: Template name (e.g., 'debian-12-standard')

        Returns:
            Full template filename (e.g., 'debian-12-standard_12.12-1_amd64.tar.zst')
            or original template if not found
        """
        if self.mock:
            return f'{template}.tar.zst'

        try:
            result = subprocess.run(
                ['pveam', 'list', 'local'],
                capture_output=True,
                text=True,
                check=True
            )
            # Find line containing the template name
            for line in result.stdout.splitlines():
                if template in line and 'vztmpl' in line:
                    # Extract filename from line like:
                    # local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst  118.00MB
                    parts = line.split()
                    if len(parts) >= 1:
                        full_path = parts[0]  # local:vztmpl/filename.tar.zst
                        # Extract just the filename
                        filename = full_path.split('/')[-1]
                        return filename
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to resolve template filename: {e}")

        # Fallback: assume .tar.zst extension
        return f'{template}.tar.zst' if '.tar' not in template else template

    @retry(max_attempts=3, delay=5, exceptions=(subprocess.CalledProcessError,))
    def download_template(self, template: str) -> bool:
        """Download template from Proxmox repository with retry on failure.

        Args:
            template: Template name to download (e.g., 'debian-12-standard')

        Returns:
            True if download successful

        Note:
            Automatically retries up to 3 times with exponential backoff on network failures
        """
        if self.mock:
            logger.info(f"MOCK: Would download template {template}")
            return True

        config = get_config()
        logger.info(f"Downloading template {template}...")

        # Template names might need full version suffix for download
        # Try exact name first, then with .tar.zst
        template_file = template if '.tar' in template else f"{template}.tar.zst"

        try:
            result = subprocess.run(
                ['pveam', 'download', 'local', template_file],
                capture_output=True,
                text=True,
                check=True,
                timeout=config.template_download_timeout
            )
            logger.info(f"✓ Downloaded template {template}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Failed to download template {template}: {e}")
            if e.stderr:
                logger.error(f"Error output: {e.stderr}")
            raise  # Re-raise to trigger retry
        except subprocess.TimeoutExpired:
            logger.error(f"✗ Template download timed out after 10 minutes")
            raise subprocess.CalledProcessError(1, ['pveam', 'download'])

    def ensure_template_available(self, template: str) -> bool:
        """Ensure template is available locally, download if needed.

        Args:
            template: Template name

        Returns:
            True if template is available (already existed or downloaded successfully)
        """
        if self.template_exists_locally(template):
            logger.debug(f"Template {template} already available")
            return True

        logger.info(f"Template {template} not found locally, downloading...")
        return self.download_template(template)
