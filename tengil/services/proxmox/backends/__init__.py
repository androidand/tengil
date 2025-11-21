"""Container backend implementations for Proxmox.

Tengil supports multiple container backends:
- LXC: Traditional LXC containers (default, mature)
- OCI: OCI containers via skopeo + LXC (Proxmox 9.1+)
"""
from .base import ContainerBackend
from .lxc import LXCBackend
from .oci import OCIBackend

__all__ = ['ContainerBackend', 'LXCBackend', 'OCIBackend']
