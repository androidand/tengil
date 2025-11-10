"""Tengil runtime configuration and settings."""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class TengilConfig:
    """Runtime configuration for Tengil operations.

    Attributes:
        post_install_timeout: Timeout in seconds for post-install tasks (default: 600)
        container_boot_timeout: Timeout in seconds for container boot (default: 30)
        template_download_timeout: Timeout in seconds for template downloads (default: 600)
        command_check_timeout: Timeout in seconds for command existence checks (default: 5)
        container_ready_timeout: Timeout in seconds for container ready checks (default: 2)
        discovery_timeout: Timeout in seconds for discovery operations (default: 10)
    """

    # Post-install timeouts
    post_install_timeout: int = 600  # 10 minutes for installing apps
    container_boot_timeout: int = 30  # 30 seconds for container to boot
    command_check_timeout: int = 5  # 5 seconds to check if command exists
    container_ready_timeout: int = 2  # 2 seconds for ready check

    # Download timeouts
    template_download_timeout: int = 600  # 10 minutes for large template downloads

    # Discovery timeouts
    discovery_timeout: int = 10  # 10 seconds for discovery operations

    @classmethod
    def from_env(cls) -> "TengilConfig":
        """Create config from environment variables.

        Environment variables:
            TENGIL_POST_INSTALL_TIMEOUT: Post-install timeout in seconds
            TENGIL_CONTAINER_BOOT_TIMEOUT: Container boot timeout in seconds
            TENGIL_TEMPLATE_DOWNLOAD_TIMEOUT: Template download timeout in seconds

        Returns:
            TengilConfig instance with values from environment or defaults
        """
        return cls(
            post_install_timeout=int(
                os.getenv("TENGIL_POST_INSTALL_TIMEOUT", cls.post_install_timeout)
            ),
            container_boot_timeout=int(
                os.getenv("TENGIL_CONTAINER_BOOT_TIMEOUT", cls.container_boot_timeout)
            ),
            template_download_timeout=int(
                os.getenv("TENGIL_TEMPLATE_DOWNLOAD_TIMEOUT", cls.template_download_timeout)
            ),
            command_check_timeout=int(
                os.getenv("TENGIL_COMMAND_CHECK_TIMEOUT", cls.command_check_timeout)
            ),
            container_ready_timeout=int(
                os.getenv("TENGIL_CONTAINER_READY_TIMEOUT", cls.container_ready_timeout)
            ),
            discovery_timeout=int(
                os.getenv("TENGIL_DISCOVERY_TIMEOUT", cls.discovery_timeout)
            ),
        )


# Global config instance (can be overridden)
_config: Optional[TengilConfig] = None


def get_config() -> TengilConfig:
    """Get the global Tengil configuration.

    Returns:
        TengilConfig instance (creates from environment if not set)
    """
    global _config
    if _config is None:
        _config = TengilConfig.from_env()
    return _config


def set_config(config: TengilConfig):
    """Set the global Tengil configuration.

    Args:
        config: TengilConfig instance to use globally
    """
    global _config
    _config = config
