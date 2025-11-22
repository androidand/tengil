#!/usr/bin/env python3
"""Tengil CLI - Declarative infrastructure for Proxmox homelabs."""

import typer
from rich.console import Console

from tengil.cli_app_commands import register_app_commands
from tengil.cli_apps_discovery_commands import register_apps_commands
from tengil.cli_compose_commands import register_compose_commands
from tengil.cli_container_commands import register_container_commands
from tengil.cli_core_commands import register_core_commands
from tengil.cli_discover_commands import register_discover_commands
from tengil.cli_drift_commands import register_drift_commands
from tengil.cli_env_commands import register_env_commands
from tengil.cli_git_commands import register_git_commands
from tengil.cli_import_commands import register_import_commands
from tengil.cli_oci_commands import register_oci_commands
from tengil.core.logger import get_logger
from tengil.core.template_loader import TemplateLoader

app = typer.Typer(
    name="tengil",
    help="""Tengil - Declarative infrastructure for Proxmox homelabs

One YAML file. Storage + containers + shares.

Quick start:
  tg packages list                # Browse preset packages
  tg init --package media-server  # Start from a package
  tg diff                         # See what will change
  tg apply                        # Make it happen

More commands: tg --help
""",
    add_completion=False,
)

console = Console()
logger = get_logger(__name__)
template_loader = TemplateLoader()

# Attach modular subcommands
register_core_commands(app, console, template_loader)
register_app_commands(app, console)
register_apps_commands(app, console)
register_container_commands(app, console)
register_env_commands(app, console)
register_compose_commands(app, console)
register_discover_commands(app, console)
register_drift_commands(app, console)
register_git_commands(app, console)
register_import_commands(app, console)
register_oci_commands(app, console)

if __name__ == "__main__":
    app()
