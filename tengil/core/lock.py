"""Concurrent access locking for Tengil operations.

Prevents multiple tg apply operations from running simultaneously.
"""
import os
import time
import fcntl
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class LockError(Exception):
    """Raised when unable to acquire lock."""
    pass


class TengilLock:
    """File-based lock for preventing concurrent apply operations."""

    def __init__(self, lock_file: Optional[Path] = None, timeout: int = 0):
        """Initialize lock.

        Args:
            lock_file: Path to lock file (default: /var/run/tengil/apply.lock)
            timeout: Seconds to wait for lock (0 = fail immediately)
        """
        if lock_file is None:
            lock_dir = Path("/var/run/tengil")
            lock_dir.mkdir(parents=True, exist_ok=True)
            lock_file = lock_dir / "apply.lock"

        self.lock_file = Path(lock_file)
        self.timeout = timeout
        self.lock_fd = None

    def acquire(self) -> bool:
        """Acquire the lock.

        Returns:
            True if lock acquired successfully

        Raises:
            LockError: If unable to acquire lock
        """
        # Create parent directory if needed
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

        # Open lock file
        self.lock_fd = open(self.lock_file, 'w')

        # Try to acquire lock
        start_time = time.time()
        while True:
            try:
                # Try non-blocking lock
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                # Write PID to lock file
                self.lock_fd.write(f"{os.getpid()}\n")
                self.lock_fd.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                self.lock_fd.flush()

                logger.debug(f"Acquired lock: {self.lock_file}")
                return True

            except (IOError, OSError) as e:
                # Lock is held by another process
                if self.timeout == 0:
                    # Read lock file to see who has it
                    lock_info = self._read_lock_info()
                    raise LockError(
                        f"Another Tengil operation is in progress.\n"
                        f"Lock held by PID {lock_info['pid']} since {lock_info['time']}\n"
                        f"Wait for the other operation to complete, or remove {self.lock_file} if stale."
                    )

                # Check if timeout exceeded
                elapsed = time.time() - start_time
                if elapsed >= self.timeout:
                    lock_info = self._read_lock_info()
                    raise LockError(
                        f"Timeout waiting for lock after {self.timeout}s.\n"
                        f"Lock held by PID {lock_info['pid']} since {lock_info['time']}"
                    )

                # Wait and retry
                time.sleep(0.5)

    def release(self):
        """Release the lock."""
        if self.lock_fd is not None:
            try:
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
                self.lock_fd.close()
                logger.debug(f"Released lock: {self.lock_file}")
            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")
            finally:
                self.lock_fd = None

            # Clean up lock file
            try:
                if self.lock_file.exists():
                    self.lock_file.unlink()
            except Exception as e:
                logger.warning(f"Error removing lock file: {e}")

    def _read_lock_info(self) -> dict:
        """Read info from lock file about who holds it."""
        try:
            with open(self.lock_file, 'r') as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    return {
                        'pid': lines[0].strip(),
                        'time': lines[1].strip()
                    }
        except Exception:
            pass

        return {'pid': 'unknown', 'time': 'unknown'}

    def __enter__(self):
        """Context manager entry."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
        return False


@contextmanager
def apply_lock(timeout: int = 0):
    """Context manager for apply operation locking.

    Args:
        timeout: Seconds to wait for lock (0 = fail immediately)

    Usage:
        with apply_lock():
            # Your apply logic here
            pass

    Raises:
        LockError: If unable to acquire lock
    """
    lock = TengilLock(timeout=timeout)
    try:
        lock.acquire()
        yield lock
    finally:
        lock.release()


def check_lock_status() -> Optional[dict]:
    """Check if apply lock is currently held.

    Returns:
        Dict with lock info if held, None if free
    """
    lock_file = Path("/var/run/tengil/apply.lock")
    if not lock_file.exists():
        return None

    # Try to open and check if locked
    try:
        with open(lock_file, 'r') as f:
            # Try to acquire non-blocking lock
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                # Lock is free (stale lock file)
                return None
            except (IOError, OSError):
                # Lock is held
                f.seek(0)
                lines = f.readlines()
                if len(lines) >= 2:
                    return {
                        'pid': lines[0].strip(),
                        'time': lines[1].strip(),
                        'lock_file': str(lock_file)
                    }
                return {'pid': 'unknown', 'time': 'unknown', 'lock_file': str(lock_file)}
    except Exception as e:
        logger.warning(f"Error checking lock status: {e}")
        return None
