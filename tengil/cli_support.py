"""Shared utilities for Tengil CLI modules."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple, Any
import typer
from rich.console import Console

from tengil.services.proxmox.containers import ContainerOrchestrator

# Default config search paths (ordered by proximity to current run)
CONFIG_PATHS = [
    "./tengil.yml",
    str(Path.home() / "tengil-configs" / "tengil.yml"),
    "/etc/tengil/tengil.yml",
]


def find_config(config_path: Optional[str] = None) -> str:
    """Locate the active Tengil configuration file."""
    if config_path:
        return config_path

    if env_config := os.environ.get("TENGIL_CONFIG"):
        return env_config

    for path in CONFIG_PATHS:
        if Path(path).exists():
            return path

    return "tengil.yml"


def is_mock() -> bool:
    """Return True when CLI runs in mock mode."""
    return os.environ.get("TG_MOCK") == "1"


def setup_file_logging(log_file: Optional[str] = None, verbose: bool = False) -> None:
    """Set up file logging for CLI commands.

    Args:
        log_file: Path to log file (optional)
        verbose: Enable verbose logging
    """
    from tengil.core.logger import setup_file_logging as _setup_file_logging
    _setup_file_logging(log_file=log_file, verbose=verbose)


def load_config_and_orchestrate(
    config_path: Optional[str],
    dry_run: bool = False
) -> Tuple[Any, Any, Any, Any]:
    """Load configuration and set up orchestration.

    Returns:
        Tuple of (loader, all_desired, all_current, container_mgr)
    """
    from tengil.config.loader import ConfigLoader
    from tengil.core.zfs_manager import ZFSManager
    from tengil.core.orchestrator import PoolOrchestrator
    from tengil.services.proxmox.containers import ContainerOrchestrator

    # Load configuration
    config_file = find_config(config_path)
    loader = ConfigLoader(config_file)
    config = loader.load()

    # Flatten all pools into full dataset paths
    orchestrator = PoolOrchestrator(loader, ZFSManager(mock=dry_run))
    all_desired, all_current = orchestrator.flatten_pools()

    # Initialize container manager
    container_mgr = ContainerOrchestrator(mock=dry_run)

    return loader, all_desired, all_current, container_mgr


def confirm_action(message: str, yes_flag: bool = False, mock: bool = False) -> bool:
    """Prompt user for confirmation unless --yes or mock mode.

    Args:
        message: Confirmation message to display
        yes_flag: Skip prompt if True (from --yes flag)
        mock: Skip prompt if True (mock mode)

    Returns:
        True if confirmed, False otherwise
    """
    if yes_flag or mock:
        return True
    return typer.confirm(message)


def handle_cli_error(
    e: Exception,
    console: Console,
    verbose: bool = False,
    exit_code: int = 1
) -> None:
    """Handle CLI errors with consistent formatting.

    Args:
        e: Exception to handle
        console: Rich console for output
        verbose: Show exception traceback if True
        exit_code: Exit code to use
    """
    console.print(f"[red]Error:[/red] {e}")
    if verbose:
        console.print_exception()
    raise typer.Exit(exit_code)


def resolve_container(
    container: str,
    orchestrator: Any,
    console: Console
) -> Tuple[int, str]:
    """Resolve container name/VMID to VMID and display name.

    Args:
        container: Container name or VMID string
        orchestrator: ContainerOrchestrator instance
        console: Rich console for error output

    Returns:
        Tuple of (vmid, display_name)

    Raises:
        typer.Exit: If container not found
    """
    if container.isdigit():
        vmid = int(container)
        display_name = f"ct{vmid}"
    else:
        # Find by name
        containers = orchestrator.list_containers()
        vmid = None
        for ct in containers:
            if ct['name'] == container:
                vmid = ct['vmid']
                display_name = container
                break

        if vmid is None:
            console.print(f"[red]Container '{container}' not found[/red]")
            raise typer.Exit(1)

    return vmid, display_name


def get_container_orchestrator(mock: Optional[bool] = None) -> ContainerOrchestrator:
    """Return a ContainerOrchestrator with mock defaults."""
    if mock is None:
        mock = is_mock()
    return ContainerOrchestrator(mock=mock)


def print_success(console: Console, message: str, prefix: str = "✓") -> None:
    """Print success message with consistent formatting.

    Args:
        console: Rich console for output
        message: Success message
        prefix: Prefix symbol (default: ✓)
    """
    console.print(f"[green]{prefix}[/green] {message}")


def print_error(console: Console, message: str, prefix: str = "✗") -> None:
    """Print error message with consistent formatting.

    Args:
        console: Rich console for output
        message: Error message
        prefix: Prefix symbol (default: ✗)
    """
    console.print(f"[red]{prefix}[/red] {message}")


def print_warning(console: Console, message: str, prefix: str = "⚠") -> None:
    """Print warning message with consistent formatting.

    Args:
        console: Rich console for output
        message: Warning message
        prefix: Prefix symbol (default: ⚠)
    """
    console.print(f"[yellow]{prefix}[/yellow] {message}")


def print_info(console: Console, message: str, prefix: str = "ℹ") -> None:
    """Print info message with consistent formatting.

    Args:
        console: Rich console for output
        message: Info message
        prefix: Prefix symbol (default: ℹ)
    """
    console.print(f"[cyan]{prefix}[/cyan] {message}")
