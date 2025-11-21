"""Abstract base class for container backends."""
from abc import ABC, abstractmethod
from typing import Dict, Optional


class ContainerBackend(ABC):
    """Abstract interface for container backends (LXC, OCI, etc.)."""

    def __init__(self, mock: bool = False):
        """Initialize backend.
        
        Args:
            mock: If True, simulate operations without making real changes
        """
        self.mock = mock

    @abstractmethod
    def create_container(
        self,
        spec: Dict,
        storage: str = 'local-lvm',
        pool: Optional[str] = None,
        **kwargs
    ) -> Optional[int]:
        """Create a new container from specification.
        
        Args:
            spec: Container specification dict
            storage: Storage backend for rootfs
            pool: Resource pool name (optional)
            **kwargs: Backend-specific options
            
        Returns:
            Container VMID if successful, None if failed
        """
        pass

    @abstractmethod
    def start_container(self, vmid: int) -> bool:
        """Start a container.
        
        Args:
            vmid: Container ID
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def stop_container(self, vmid: int, timeout: int = 30) -> bool:
        """Stop a container.
        
        Args:
            vmid: Container ID
            timeout: Shutdown timeout in seconds
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def destroy_container(self, vmid: int, purge: bool = False) -> bool:
        """Destroy a container.
        
        Args:
            vmid: Container ID
            purge: If True, also remove from backups/replication
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def container_exists(self, vmid: int) -> bool:
        """Check if container exists.
        
        Args:
            vmid: Container ID
            
        Returns:
            True if container exists, False otherwise
        """
        pass

    @abstractmethod
    def configure_gpu(self, vmid: int, gpu_type: Optional[str] = None) -> bool:
        """Configure GPU passthrough for container.
        
        Args:
            vmid: Container ID
            gpu_type: GPU type hint (intel, nvidia, amd)
            
        Returns:
            True if successful, False otherwise
        """
        pass
