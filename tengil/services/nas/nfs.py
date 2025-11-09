"""NFS export management."""
import subprocess
from pathlib import Path
from typing import Dict

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class NFSManager:
    """Manages NFS exports."""

    def __init__(self, mock: bool = False):
        self.mock = mock
        self.nfs_exports_path = Path('/etc/exports')
        self.exports_d_path = Path('/etc/exports.d')

    def parse_nfs_exports(self) -> Dict[str, Dict]:
        """Parse existing NFS exports."""
        if self.mock:
            logger.info("MOCK: Would parse /etc/exports")
            return {}

        exports = {}

        # Check main exports file
        if self.nfs_exports_path.exists():
            exports.update(self._parse_exports_file(self.nfs_exports_path))

        # Check exports.d directory
        if self.exports_d_path.exists():
            for export_file in self.exports_d_path.glob('*.exports'):
                exports.update(self._parse_exports_file(export_file))

        return exports

    def _parse_exports_file(self, path: Path) -> Dict[str, Dict]:
        """Parse a single exports file."""
        exports = {}

        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue

                    # Parse export line
                    parts = line.split()
                    if len(parts) >= 2:
                        export_path = parts[0]
                        clients = []

                        for part in parts[1:]:
                            if '(' in part:
                                # Client with options
                                client, options = part.split('(', 1)
                                options = options.rstrip(')')
                                clients.append({
                                    'client': client,
                                    'options': options
                                })
                            else:
                                # Client without options
                                clients.append({
                                    'client': part,
                                    'options': 'ro'
                                })

                        exports[export_path] = {'clients': clients}

        except Exception as e:
            logger.error(f"Failed to parse exports file {path}: {e}")

        return exports

    def add_nfs_export(self, path: str, config: Dict) -> bool:
        """Add or update an NFS export."""
        if self.mock:
            logger.info(f"MOCK: Would add NFS export for {path}")
            return True

        try:
            # Check if NFS is installed
            if not self._check_nfs_installed():
                logger.warning("NFS server is not installed")
                return False

            # Prepare export line
            options = config.get('options', 'rw,sync,no_subtree_check')
            allowed = config.get('allowed', '*')

            # Build export line
            export_line = f"{path} {allowed}({options})\n"

            # Use exports.d for better organization (if available)
            if self.exports_d_path.exists():
                export_file = self.exports_d_path / 'tengil.exports'

                # Read existing tengil exports
                existing_exports = []
                if export_file.exists():
                    with open(export_file, 'r') as f:
                        for line in f:
                            # Skip if it's the same path
                            if not line.strip().startswith(path + ' '):
                                existing_exports.append(line)

                # Add new export
                existing_exports.append(export_line)

                # Write back
                with open(export_file, 'w') as f:
                    f.write("# Tengil-managed NFS exports\n")
                    f.writelines(existing_exports)

            else:
                # Fall back to main exports file
                existing_exports = []
                if self.nfs_exports_path.exists():
                    with open(self.nfs_exports_path, 'r') as f:
                        for line in f:
                            # Skip if it's the same path
                            if not line.strip().startswith(path + ' '):
                                existing_exports.append(line)

                # Add new export
                existing_exports.append(export_line)

                # Write back
                with open(self.nfs_exports_path, 'w') as f:
                    f.writelines(existing_exports)

            # Reload NFS exports
            self._reload_nfs()

            logger.info(f"Added NFS export for {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to add NFS export: {e}")
            return False

    def remove_nfs_export(self, path: str) -> bool:
        """Remove an NFS export."""
        if self.mock:
            logger.info(f"MOCK: Would remove NFS export for {path}")
            return True

        try:
            modified = False

            # Check exports.d
            if self.exports_d_path.exists():
                export_file = self.exports_d_path / 'tengil.exports'
                if export_file.exists():
                    lines = []
                    with open(export_file, 'r') as f:
                        for line in f:
                            if not line.strip().startswith(path + ' '):
                                lines.append(line)
                            else:
                                modified = True

                    if modified:
                        with open(export_file, 'w') as f:
                            f.writelines(lines)

            # Check main exports file
            if self.nfs_exports_path.exists():
                lines = []
                with open(self.nfs_exports_path, 'r') as f:
                    for line in f:
                        if not line.strip().startswith(path + ' '):
                            lines.append(line)
                        else:
                            modified = True

                if modified:
                    with open(self.nfs_exports_path, 'w') as f:
                        f.writelines(lines)

            if modified:
                self._reload_nfs()
                logger.info(f"Removed NFS export for {path}")

            return True

        except Exception as e:
            logger.error(f"Failed to remove NFS export: {e}")
            return False

    def _check_nfs_installed(self) -> bool:
        """Check if NFS server is installed."""
        return Path('/usr/sbin/rpc.nfsd').exists() or Path('/sbin/rpc.nfsd').exists()

    def _reload_nfs(self) -> bool:
        """Reload NFS exports."""
        if self.mock:
            logger.info("MOCK: Would reload NFS exports")
            return True

        try:
            # Export the new configuration
            result = subprocess.run(
                ["exportfs", "-ra"],
                capture_output=True,
                check=False
            )

            if result.returncode == 0:
                logger.info("Reloaded NFS exports")
                return True
            else:
                logger.warning(f"Failed to reload NFS exports: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Failed to reload NFS exports: {e}")
            return False
