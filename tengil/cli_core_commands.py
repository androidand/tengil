"""Core Tengil CLI commands orchestrator - delegates to specialized modules.

This module serves as a thin orchestrator that registers all core commands
from their respective modules. The actual command implementations live in:
- cli_state_commands.py: scan, diff, apply (state management)
- cli_setup_commands.py: init, add, import (setup/initialization)  
- cli_recovery_commands.py: snapshot, rollback (recovery operations)
- cli_utility_commands.py: suggest, doctor, version (utility commands)
- cli_package_commands.py: install, templates, packages (package management)

This follows the established pattern from other CLI modules like:
- cli_app_commands.py (182 lines)
- cli_discover_commands.py (215 lines)
- cli_container_commands.py (151 lines)
"""
from typing import Optional

import typer
from rich.console import Console

from tengil.cli_state_commands import register_state_commands
from tengil.cli_setup_commands import register_setup_commands
from tengil.cli_recovery_commands import register_recovery_commands
from tengil.cli_utility_commands import register_utility_commands
from tengil.cli_package_commands import register_package_commands
from tengil.core.template_loader import TemplateLoader


def register_core_commands(
    app: typer.Typer,
    shared_console: Console,
    shared_template_loader: Optional[TemplateLoader] = None,
):
    """Register all core commands with the main Typer app.

    This is the main entry point that delegates to specialized command modules.
    Each module handles a specific domain:
    - State: scan, diff, apply
    - Setup: init, add, import
    - Recovery: snapshot, rollback
    - Utility: suggest, doctor, version
    - Package: install, templates, packages

    Args:
        app: Main Typer application
        shared_console: Shared Rich console instance
        shared_template_loader: Preconfigured template loader from main CLI (optional)
    """
    # Register commands from each specialized module
    register_state_commands(app, shared_console, shared_template_loader)
    register_setup_commands(app, shared_console, shared_template_loader)
    register_recovery_commands(app, shared_console, shared_template_loader)
    register_utility_commands(app, shared_console, shared_template_loader)
    register_package_commands(app, shared_console, shared_template_loader)
