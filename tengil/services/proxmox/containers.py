"""Proxmox container management - backward compatibility wrapper.

This module provides backward compatibility for code importing from the old location.
The implementation has been refactored into focused classes in the containers/ package.

DEPRECATED: Import from tengil.services.proxmox.containers instead:
    from tengil.services.proxmox.containers import ContainerManager
"""
import warnings

from .containers import (
    ContainerDiscovery,
    ContainerLifecycle,
    ContainerManager,
    ContainerOrchestrator,
    MountManager,
    TemplateManager,
)

# Show deprecation warning when imported directly
warnings.warn(
    "Importing from tengil.services.proxmox.containers is deprecated. "
    "Import from tengil.services.proxmox.containers package instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = [
    'ContainerManager',
    'ContainerOrchestrator',
    'ContainerLifecycle',
    'ContainerDiscovery',
    'MountManager',
    'TemplateManager',
]
