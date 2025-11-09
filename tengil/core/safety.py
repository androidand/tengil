"""Safety module to prevent accidental data destruction.

This module provides safeguards against destructive operations and ensures
Tengil never accidentally destroys user data.
"""
from typing import List
from pathlib import Path
import subprocess

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class SafetyGuard:
    """Prevents destructive operations and enforces safety policies."""
    
    # Operations that are NEVER allowed
    FORBIDDEN_OPERATIONS = [
        'zfs destroy',
        'zfs delete', 
        'rm -rf',
        'rmdir',
        'unlink'
    ]
    
    def __init__(self, mock: bool = False):
        self.mock = mock
        self._destruction_enabled = False  # Must be explicitly enabled
    
    def check_command_safety(self, command: List[str]) -> bool:
        """Verify command doesn't contain destructive operations.
        
        Args:
            command: Command to check
            
        Returns:
            True if safe, False if potentially destructive
            
        Raises:
            SafetyError: If command contains forbidden operations
        """
        cmd_str = ' '.join(command).lower()
        
        for forbidden in self.FORBIDDEN_OPERATIONS:
            if forbidden in cmd_str:
                raise SafetyError(
                    f"Forbidden operation detected: {forbidden}\n"
                    f"Command: {cmd_str}\n"
                    f"Tengil is designed to NEVER destroy data.\n"
                    f"If you need to delete datasets, do it manually with: zfs destroy"
                )
        
        return True
    
    def require_confirmation(self, operation: str, resource: str) -> bool:
        """Require user confirmation for sensitive operations.
        
        Args:
            operation: Description of operation
            resource: Resource being affected
            
        Returns:
            True if user confirms, False otherwise
        """
        print(f"\n⚠️  SAFETY CHECK")
        print(f"Operation: {operation}")
        print(f"Resource: {resource}")
        print(f"\nThis will make changes to your system.")
        response = input("Continue? [y/N]: ").lower().strip()
        
        return response == 'y'
    
    def create_safety_snapshot(self, dataset: str) -> bool:
        """Create safety snapshot before modifications.
        
        Args:
            dataset: Dataset to snapshot
            
        Returns:
            True if snapshot created successfully
        """
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        snapshot_name = f"{dataset}@tengil_safety_{timestamp}"
        
        if self.mock:
            logger.info(f"MOCK: Would create safety snapshot {snapshot_name}")
            return True
        
        try:
            cmd = ["zfs", "snapshot", snapshot_name]
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Created safety snapshot: {snapshot_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create safety snapshot: {e}")
            return False
    
    def verify_no_data_loss(self, operation: str, details: dict) -> None:
        """Final verification that operation won't lose data.
        
        Args:
            operation: Operation being performed
            details: Details about the operation
            
        Raises:
            SafetyError: If operation could cause data loss
        """
        # Check for any potentially destructive patterns
        dangerous_keywords = ['delete', 'destroy', 'remove', 'purge', 'wipe']
        
        for keyword in dangerous_keywords:
            if keyword in operation.lower():
                raise SafetyError(
                    f"Operation '{operation}' contains dangerous keyword: {keyword}\n"
                    f"Tengil will not perform this operation.\n"
                    f"Data preservation is our highest priority."
                )
        
        logger.debug(f"Safety check passed for operation: {operation}")


class SafetyError(Exception):
    """Raised when a safety check fails."""
    pass


class ReadOnlyMode:
    """Context manager for read-only operations."""
    
    def __init__(self, reason: str):
        self.reason = reason
        self._original_mode = None
    
    def __enter__(self):
        logger.info(f"Entering read-only mode: {self.reason}")
        # Could set global flags here if needed
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.info("Exiting read-only mode")
        return False


# Global safety guard instance
_safety_guard = None

def get_safety_guard(mock: bool = False) -> SafetyGuard:
    """Get or create the global safety guard instance."""
    global _safety_guard
    if _safety_guard is None:
        _safety_guard = SafetyGuard(mock=mock)
    return _safety_guard
