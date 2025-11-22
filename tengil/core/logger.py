"""Unified logging for Tengil with console and file output."""
import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

console = Console()

# Log file configuration
LOG_DIR = Path("/var/log/tengil")
LOG_FILE = LOG_DIR / "tengil.log"

# Track if file logging has been set up
_file_logging_configured = False


def setup_file_logging(log_file: str = None, verbose: bool = False):
    """Set up file logging for Tengil operations.

    Args:
        log_file: Path to log file (defaults to /var/log/tengil/tengil.log)
        verbose: Enable debug-level logging

    Note:
        Creates log directory if it doesn't exist.
        Falls back to /tmp if /var/log/tengil is not writable.
    """
    global _file_logging_configured

    if _file_logging_configured:
        return

    # Determine log file path
    target_log_file = Path(log_file) if log_file else LOG_FILE

    # Try to create log directory
    try:
        target_log_file.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Fallback to /tmp if /var/log is not writable
        target_log_file = Path("/tmp/tengil.log")
        target_log_file.parent.mkdir(parents=True, exist_ok=True)

    # Set up file handler for root tengil logger
    root_logger = logging.getLogger("tengil")
    file_handler = logging.FileHandler(target_log_file)
    file_handler.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Detailed format for file logs
    file_formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Set root logger level
    root_logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    _file_logging_configured = True

    # Log the initialization
    root_logger.info(f"Tengil logging initialized: {target_log_file}")


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance with console output.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger with Rich console handler

    Note:
        File logging must be enabled separately via setup_file_logging()
    """
    logger = logging.getLogger(name)

    # Only add console handler if not already present
    if not any(isinstance(h, RichHandler) for h in logger.handlers):
        handler = RichHandler(console=console, show_path=False)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
