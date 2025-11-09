"""ACL and permissions management."""
import os
import pwd
import grp
import subprocess
from pathlib import Path
from typing import Dict

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class ACLManager:
    """Manages filesystem ACLs and permissions."""

    def __init__(self, mock: bool = False):
        self.mock = mock

    def set_dataset_permissions(self, path: str, config: Dict) -> bool:
        """Set appropriate permissions and ACLs for a dataset."""
        if self.mock:
            logger.info(f"MOCK: Would set permissions for {path}")
            return True

        try:
            dataset_path = Path(path)
            if not dataset_path.exists():
                logger.warning(f"Path does not exist: {path}")
                return False

            # Default permissions
            uid = config.get('uid', 'nobody')
            gid = config.get('gid', 'nogroup')
            mode = config.get('mode', '0775')

            # Convert user/group names to IDs
            try:
                if isinstance(uid, str):
                    uid = pwd.getpwnam(uid).pw_uid
                if isinstance(gid, str):
                    gid = grp.getgrnam(gid).gr_gid
            except KeyError as e:
                logger.error(f"Invalid user/group: {e}")
                return False

            # Set ownership
            os.chown(path, uid, gid)

            # Set permissions
            if isinstance(mode, str):
                mode = int(mode, 8)
            os.chmod(path, mode)

            # Set ACLs if specified
            if 'acl' in config:
                self._set_acls(path, config['acl'])

            logger.info(f"Set permissions for {path}: uid={uid}, gid={gid}, mode={oct(mode)}")
            return True

        except Exception as e:
            logger.error(f"Failed to set permissions: {e}")
            return False

    def _set_acls(self, path: str, acl_config: Dict) -> bool:
        """Set POSIX ACLs on a path."""
        if self.mock:
            return True

        try:
            # Check if ACL tools are available
            if not Path('/usr/bin/setfacl').exists():
                logger.warning("ACL tools not installed (setfacl not found)")
                return False

            acl_type = acl_config.get('type', 'posixacl')

            if acl_type != 'posixacl':
                logger.warning(f"Unsupported ACL type: {acl_type}")
                return False

            # Apply ACL entries
            for entry in acl_config.get('entries', []):
                cmd = ['setfacl', '-m', entry, path]
                subprocess.run(cmd, check=True)
                logger.info(f"Applied ACL to {path}: {entry}")

            # Set default ACLs for directories
            if Path(path).is_dir() and acl_config.get('recursive', False):
                for entry in acl_config.get('entries', []):
                    if not entry.startswith('default:'):
                        default_entry = f"default:{entry}"
                        cmd = ['setfacl', '-m', default_entry, path]
                        subprocess.run(cmd, check=True)

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set ACLs: {e}")
            return False
