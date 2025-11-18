"""Container configuration models."""
from dataclasses import dataclass, field
from typing import Optional, Dict, List


@dataclass
class NetworkConfig:
    """Network configuration for a container."""
    bridge: str = "vmbr0"
    ip: str = "dhcp"  # Can be "dhcp" or CIDR like "192.168.1.100/24"
    gateway: Optional[str] = None
    firewall: bool = True


@dataclass
class ContainerResources:
    """Resource allocation for a container."""
    memory: int = 2048  # MB
    cores: int = 2
    disk: str = "8G"
    swap: int = 512  # MB
    pool: Optional[str] = None  # Proxmox resource pool for organization


@dataclass
class ContainerMount:
    """Configuration for mounting a dataset to a container.

    Phase 1: Simple mounts to existing containers
    Phase 2+: Full container lifecycle with auto_create
    """
    # Identity (at least one required)
    vmid: Optional[int] = None
    name: Optional[str] = None  # Alternative to vmid - Tengil will find it

    # Mount configuration
    mount: str = None  # Mount point inside container (required)
    readonly: bool = True  # Safety first!

    # Phase 2: Auto-creation (not yet implemented)
    auto_create: bool = False
    template: Optional[str] = None  # e.g., "debian-12-standard"
    resources: Optional[ContainerResources] = None
    network: Optional[NetworkConfig] = None
    pool: Optional[str] = None  # Resource pool (can also be in resources)
    privileged: bool = False  # Privileged container (default: unprivileged for security)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    startup_order: Optional[int] = None
    startup_delay: Optional[int] = None
    startup: Optional[str] = None  # Direct pct startup string override

    # Phase 3: Post-install automation (not yet implemented)
    setup_commands: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate container configuration."""
        if not self.vmid and not self.name:
            raise ValueError("Container must have either vmid or name")
        
        if not self.mount:
            raise ValueError("Container must specify a mount point")
        
        if self.auto_create and not self.template:
            raise ValueError("auto_create requires template to be specified")


@dataclass
class ContainerInfo:
    """Runtime information about a container."""
    vmid: int
    name: str
    status: str  # running, stopped, etc.
    template: Optional[str] = None
    memory: Optional[int] = None
    cores: Optional[int] = None
    uptime: Optional[int] = None
    
    @property
    def is_running(self) -> bool:
        """Check if container is running."""
        return self.status == "running"
