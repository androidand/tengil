"""SMB/Samba share management."""
import subprocess
from pathlib import Path
from typing import Dict, List

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class SMBManager:
    """Manages SMB/Samba shares."""

    def __init__(self, mock: bool = False):
        self.mock = mock
        self.smb_conf_path = Path('/etc/samba/smb.conf')

    def parse_smb_conf(self) -> Dict[str, Dict]:
        """Parse existing SMB configuration."""
        if self.mock:
            logger.info("MOCK: Would parse /etc/samba/smb.conf")
            return {}

        if not self.smb_conf_path.exists():
            logger.warning(f"SMB config not found: {self.smb_conf_path}")
            return {}

        shares = {}
        current_share = None

        try:
            with open(self.smb_conf_path, 'r') as f:
                for line in f:
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith('#') or line.startswith(';'):
                        continue

                    # Share definition
                    if line.startswith('[') and line.endswith(']'):
                        share_name = line[1:-1]
                        # Skip global and other special sections
                        if share_name.lower() not in ['global', 'homes', 'printers', 'print$']:
                            current_share = share_name
                            shares[share_name] = {}

                    # Share properties
                    elif current_share and '=' in line:
                        key, value = line.split('=', 1)
                        shares[current_share][key.strip()] = value.strip()

        except Exception as e:
            logger.error(f"Failed to parse smb.conf: {e}")

        return shares

    def add_smb_share(self, name: str, path: str, config: Dict) -> bool:
        """Add or update an SMB share."""
        if self.mock:
            logger.info(f"MOCK: Would add SMB share '{name}' at {path}")
            return True

        try:
            # Check if samba is installed
            if not self._check_samba_installed():
                logger.warning("Samba is not installed")
                return False

            # Read existing configuration
            if self.smb_conf_path.exists():
                with open(self.smb_conf_path, 'r') as f:
                    lines = f.readlines()
            else:
                lines = self._get_default_smb_global()

            # Check if share already exists
            share_start = -1
            share_end = -1
            for i, line in enumerate(lines):
                if line.strip() == f"[{name}]":
                    share_start = i
                elif share_start >= 0 and line.strip().startswith('['):
                    share_end = i
                    break

            # If share exists, remove it
            if share_start >= 0:
                if share_end < 0:
                    share_end = len(lines)
                logger.info(f"Updating existing SMB share '{name}'")
                lines = lines[:share_start] + lines[share_end:]
            else:
                logger.info(f"Creating new SMB share '{name}'")

            # Build new share configuration
            share_lines = [f"\n[{name}]\n"]
            share_lines.append(f"    path = {path}\n")

            # Default settings
            defaults = {
                'browseable': 'yes',
                'writable': 'yes',
                'create mask': '0664',
                'directory mask': '0775',
                'force create mode': '0664',
                'force directory mode': '0775'
            }

            # Apply config (override defaults)
            settings = defaults.copy()

            # Map our config keys to SMB directives
            if config.get('readonly', False):
                settings['writable'] = 'no'
                settings['read only'] = 'yes'

            if config.get('guest_ok', False):
                settings['guest ok'] = 'yes'
                settings['public'] = 'yes'

            if 'valid_users' in config:
                settings['valid users'] = config['valid_users']

            if config.get('browseable') is False:
                settings['browseable'] = 'no'

            # Special settings for Time Machine
            if config.get('fruit', False) or config.get('timemachine', False):
                settings['vfs objects'] = 'catia fruit streams_xattr'
                settings['fruit:time machine'] = 'yes'
                settings['fruit:metadata'] = 'stream'
                settings['fruit:model'] = 'MacSamba'
                settings['fruit:posix_rename'] = 'yes'
                settings['fruit:veto_appledouble'] = 'no'
                settings['fruit:zero_file_id'] = 'yes'
                settings['fruit:wipe_intentionally_left_blank_rfork'] = 'yes'
                settings['fruit:delete_empty_adfiles'] = 'yes'

            # Apply custom SMB options
            if 'smb_options' in config:
                settings.update(config['smb_options'])

            # Write settings
            for key, value in settings.items():
                share_lines.append(f"    {key} = {value}\n")

            # Add share to configuration
            lines.extend(share_lines)

            # Write back configuration
            with open(self.smb_conf_path, 'w') as f:
                f.writelines(lines)

            # Test configuration
            result = subprocess.run(
                ["testparm", "-s", str(self.smb_conf_path)],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error(f"Invalid SMB configuration: {result.stderr}")
                return False

            # Reload Samba
            self._reload_samba()

            return True

        except Exception as e:
            logger.error(f"Failed to add SMB share: {e}")
            return False

    def remove_smb_share(self, name: str) -> bool:
        """Remove an SMB share."""
        if self.mock:
            logger.info(f"MOCK: Would remove SMB share '{name}'")
            return True

        try:
            if not self.smb_conf_path.exists():
                return True

            with open(self.smb_conf_path, 'r') as f:
                lines = f.readlines()

            # Find and remove share
            share_start = -1
            share_end = -1
            for i, line in enumerate(lines):
                if line.strip() == f"[{name}]":
                    share_start = i
                elif share_start >= 0 and line.strip().startswith('['):
                    share_end = i
                    break

            if share_start >= 0:
                if share_end < 0:
                    share_end = len(lines)
                lines = lines[:share_start] + lines[share_end:]

                with open(self.smb_conf_path, 'w') as f:
                    f.writelines(lines)

                self._reload_samba()
                logger.info(f"Removed SMB share '{name}'")
                return True

            return True

        except Exception as e:
            logger.error(f"Failed to remove SMB share: {e}")
            return False

    def _check_samba_installed(self) -> bool:
        """Check if Samba is installed."""
        return Path('/usr/sbin/smbd').exists() or Path('/usr/bin/smbd').exists()

    def _reload_samba(self) -> bool:
        """Reload Samba configuration."""
        if self.mock:
            logger.info("MOCK: Would reload Samba")
            return True

        try:
            # Try systemctl first
            result = subprocess.run(
                ["systemctl", "reload", "smbd"],
                capture_output=True,
                check=False
            )

            if result.returncode != 0:
                # Fall back to service command
                result = subprocess.run(
                    ["service", "smbd", "reload"],
                    capture_output=True,
                    check=False
                )

            if result.returncode == 0:
                logger.info("Reloaded Samba configuration")
                return True
            else:
                logger.warning("Failed to reload Samba")
                return False

        except Exception as e:
            logger.error(f"Failed to reload Samba: {e}")
            return False

    def _get_default_smb_global(self) -> List[str]:
        """Get default Samba global configuration."""
        return [
            "[global]\n",
            "    workgroup = WORKGROUP\n",
            "    server string = Tengil NAS\n",
            "    security = user\n",
            "    map to guest = Bad User\n",
            "    log file = /var/log/samba/%m.log\n",
            "    max log size = 50\n",
            "    dns proxy = no\n",
            "    # Performance tuning\n",
            "    socket options = TCP_NODELAY IPTOS_LOWDELAY\n",
            "    read raw = yes\n",
            "    write raw = yes\n",
            "    oplocks = yes\n",
            "    max xmit = 65535\n",
            "    dead time = 15\n",
            "    getwd cache = yes\n",
            "\n"
        ]
