"""Proxmox LXC container management.

This package provides a clean separation of concerns for container operations:
- TemplateManager: Template download and availability
- ContainerDiscovery: Query container information
- ContainerLifecycle: Create, start, stop containers
- MountManager: Manage container mount points
- ContainerOrchestrator: High-level orchestration (facade)

For backward compatibility, ContainerManager is aliased to ContainerOrchestrator.
"""
from .templates import TemplateManager
from .discovery import ContainerDiscovery
from .lifecycle import ContainerLifecycle
from .mounts import MountManager
from .orchestrator import ContainerOrchestrator

# Backward compatibility: ContainerManager = ContainerOrchestrator
ContainerManager = ContainerOrchestrator

__all__ = [
    'TemplateManager',
    'ContainerDiscovery',
    'ContainerLifecycle',
    'MountManager',
    'ContainerOrchestrator',
    'ContainerManager',  # Backward compatibility
]
