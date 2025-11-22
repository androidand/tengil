"""Infrastructure import CLI commands."""
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from tengil.cli_support import is_mock
from tengil.core.importer import InfrastructureImporter

# Module-level console instance (will be set by register function)
console: Console = Console()


def import_cmd(
    pool: str = typer.Argument(..., help="ZFS pool name to import from"),
    output: Path = typer.Option(
        Path("tengil-imported.yml"), "--output", "-o", help="Output config file path"
    ),
    container_range: Optional[str] = typer.Option(
        None, "--container", "-c", help="Container VMID range (e.g., '200-210')"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be imported without writing"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Import existing Proxmox infrastructure into tengil.yml format.

    Scans your existing ZFS datasets and containers to generate a tengil.yml
    configuration file. This is useful for adopting Tengil on existing infrastructure.

    Examples:
        tg import tank                          # Import from 'tank' pool
        tg import tank -o tengil.yml            # Save to tengil.yml
        tg import tank --container 200-210      # Only import containers 200-210
        tg import tank --dry-run                # Preview without writing
    """
    from tengil.cli_support import print_error, print_info, print_success, print_warning

    console.print("[cyan]🔍 Scanning existing infrastructure...[/cyan]")

    importer = InfrastructureImporter(mock=is_mock())

    # Scan ZFS datasets
    print_info(console, f"Scanning ZFS pool: {pool}")
    datasets = importer.scan_zfs_pool(pool)

    if not datasets:
        print_error(console, f"No datasets found in pool '{pool}'")
        print_info(console, f"Create pool first: zpool create {pool} <devices>")
        raise typer.Exit(1)

    print_success(console, f"Found {len(datasets)} dataset(s)")

    # List datasets
    if verbose:
        dataset_table = Table(title="Datasets", show_header=True, header_style="bold cyan")
        dataset_table.add_column("Name")
        dataset_table.add_column("Profile")
        dataset_table.add_column("Compression")
        dataset_table.add_column("Recordsize")

        for name, props in datasets.items():
            dataset_table.add_row(
                name,
                props.get("profile", "media"),
                props.get("compression", "off"),
                props.get("recordsize", "128K"),
            )

        console.print(dataset_table)

    # Scan containers
    print_info(console, "Scanning containers...")
    containers = importer.list_containers()

    # Filter by range if specified
    if container_range:
        if "-" in container_range:
            start, end = container_range.split("-")
            start_vmid, end_vmid = int(start), int(end)
            containers = [
                ct for ct in containers if start_vmid <= ct["vmid"] <= end_vmid
            ]
        else:
            vmid = int(container_range)
            containers = [ct for ct in containers if ct["vmid"] == vmid]

    print_success(console, f"Found {len(containers)} container(s)")

    # List containers
    if containers:
        ct_table = Table(title="Containers", show_header=True, header_style="bold cyan")
        ct_table.add_column("VMID", style="bold")
        ct_table.add_column("Name")
        ct_table.add_column("Status")
        ct_table.add_column("Type")

        for ct in containers:
            # Get full config to detect type
            ct_config = importer.get_container_config(ct["vmid"])
            ct_type = ct_config.get("type", "lxc")

            ct_table.add_row(
                str(ct["vmid"]), ct["name"], ct["status"], ct_type.upper()
            )

        console.print(ct_table)

    # Generate config
    console.print("\n[cyan]📋 Generating configuration...[/cyan]")
    config = importer.generate_config(pool, interactive=False)

    if dry_run:
        print_info(console, "DRY RUN - Configuration preview:")
        import yaml

        preview = yaml.dump(config, default_flow_style=False, sort_keys=False)
        console.print(f"\n[dim]{preview}[/dim]")
        print_warning(console, f"Would write to: {output}")
        return

    # Write config
    if importer.write_config(config, output):
        print_success(console, f"Configuration written to: {output}")
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print(f"  1. Review the generated config: [yellow]cat {output}[/yellow]")
        console.print(f"  2. Adjust profiles, mounts, and container specs as needed")
        console.print(f"  3. Run a diff: [yellow]tg diff --config {output}[/yellow]")
        console.print(f"  4. Apply if satisfied: [yellow]tg apply --config {output}[/yellow]")
    else:
        print_error(console, "Failed to write configuration")
        raise typer.Exit(1)


def register_import_commands(app: typer.Typer, shared_console: Console):
    """Register import commands with the main Typer app.

    Args:
        app: Main Typer application
        shared_console: Shared Rich console instance
    """
    global console
    console = shared_console

    # Register command
    app.command(name="import")(import_cmd)
