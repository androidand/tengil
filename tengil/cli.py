#!/usr/bin/env python3
"""Tengil CLI - The overlord of your homelab."""
import typer
import os
import yaml
import subprocess
from pathlib import Path
from rich import print
from rich.console import Console
from typing import Optional, List

from tengil.config.loader import ConfigLoader
from tengil.core.zfs_manager import ZFSManager
from tengil.core.diff_engine import DiffEngine
from tengil.core.logger import get_logger
from tengil.core.orchestrator import PoolOrchestrator
from tengil.core.applicator import ChangeApplicator
from tengil.core.permission_manager import PermissionManager
from tengil.services.proxmox import ProxmoxManager
from tengil.services.nas import NASManager
from tengil.services.proxmox.containers import ContainerOrchestrator
from tengil.core.state_store import StateStore
from tengil.core.importer import InfrastructureImporter
from tengil.core.template_loader import TemplateLoader
from tengil.core.snapshot_manager import SnapshotManager
from tengil.core.recovery import RecoveryManager
from tengil.core.package_loader import PackageLoader
from tengil.recommendations import show_all_recommendations, show_dataset_recommendations
from tengil.discovery import ProxmoxDiscovery
from tengil.smart_suggestions import SmartContainerMatcher

app = typer.Typer(
    name="tengil",
    help="""Tengil - Declarative infrastructure for Proxmox homelabs

One YAML file. Storage + containers + shares.

Quick start:
  tg packages list                # Browse 12 preset packages
  tg init --package media-server  # Start from a package
  tg diff                         # See what will change
  tg apply                        # Make it happen

More commands: tg --help
""",
    add_completion=False
)

console = Console()
logger = get_logger(__name__)

# Default config search paths
CONFIG_PATHS = [
    "/etc/tengil/tengil.yml",  # System-wide config
    "./tengil.yml",             # Current directory
]

# Initialize template loader
template_loader = TemplateLoader()

def find_config(config_path: Optional[str] = None) -> str:
    """Find configuration file in search paths."""
    if config_path:
        return config_path
    
    # Check environment variable
    if env_config := os.environ.get('TENGIL_CONFIG'):
        return env_config
    
    # Search default paths
    for path in CONFIG_PATHS:
        if Path(path).exists():
            return path
    
    # Default to current directory
    return "tengil.yml"

def is_mock() -> bool:
    """Check if running in mock mode."""
    return os.environ.get('TG_MOCK') == '1'

@app.command()
def diff(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Path to log file")
):
    """Plan - Show what changes would be made (like 'terraform plan')."""
    # Set up file logging
    from tengil.core.logger import setup_file_logging
    setup_file_logging(log_file=log_file, verbose=verbose)

    try:
        # Load configuration
        config_path = find_config(config)
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        # Flatten all pools into full dataset paths
        orchestrator = PoolOrchestrator(loader, ZFSManager())
        all_desired, all_current = orchestrator.flatten_pools()
        
        # Initialize container manager for diff detection
        container_mgr = ContainerOrchestrator(mock=False)
        
        # Calculate diff across all pools (including containers)
        engine = DiffEngine(all_desired, all_current, container_manager=container_mgr)
        engine.calculate_diff()
        
        # Display plan
        if engine.changes or engine.container_changes:
            plan = engine.format_plan()
            console.print(plan)
        else:
            console.print("[green]✓[/green] All pools are up to date")
        
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)

@app.command()
def apply(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show actions without applying"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Path to log file"),
    no_checkpoint: bool = typer.Option(False, "--no-checkpoint", help="Skip automatic checkpoint creation")
):
    """Apply the configuration (like 'terraform apply').

    Automatically creates a recovery checkpoint before applying changes.
    If apply fails, you can rollback using 'tg rollback'.
    """
    # Set up file logging
    from tengil.core.logger import setup_file_logging
    setup_file_logging(log_file=log_file, verbose=verbose)

    checkpoint = None
    recovery = None

    try:
        # Load configuration
        config_path = find_config(config)
        loader = ConfigLoader(config_path)
        config = loader.load()

        # Flatten all pools into full dataset paths
        orchestrator = PoolOrchestrator(loader, ZFSManager(mock=dry_run))
        all_desired, all_current = orchestrator.flatten_pools()

        # Initialize container manager
        container_mgr = ContainerOrchestrator(mock=dry_run)

        # Calculate diff across all pools (including containers)
        engine = DiffEngine(all_desired, all_current, container_manager=container_mgr)
        changes = engine.calculate_diff()

        if not changes and not engine.container_changes:
            console.print("[green]✓[/green] Infrastructure is up to date")
            return

        # Display plan
        plan = engine.format_plan()
        console.print(plan)

        # Confirm unless --yes
        if not yes and not dry_run:
            if not typer.confirm("\nDo you want to apply these changes?"):
                console.print("[yellow]Apply cancelled[/yellow]")
                return

        if dry_run:
            console.print("\n[yellow]DRY RUN - No changes applied[/yellow]")
            return

        # Create recovery checkpoint before applying changes
        if not no_checkpoint:
            console.print("\n[dim]Creating recovery checkpoint...[/dim]")
            recovery = RecoveryManager(mock=dry_run)

            # Get list of datasets that will be affected
            datasets_to_snapshot = list(all_current.keys())  # Snapshot existing datasets

            if datasets_to_snapshot:
                try:
                    checkpoint = recovery.create_checkpoint(
                        datasets=datasets_to_snapshot,
                        name="pre-apply"
                    )
                    console.print(f"[green]✓[/green] Checkpoint created")
                    console.print(f"  [dim]Snapshots: {len(checkpoint.get('snapshots', {}))} dataset(s)[/dim]")
                    console.print(f"  [dim]Config backups: storage.cfg, smb.conf[/dim]")
                except Exception as e:
                    console.print(f"[yellow]⚠[/yellow] Checkpoint creation failed: {e}")
                    console.print("[yellow]Continuing without checkpoint (use --no-checkpoint to suppress this warning)[/yellow]")
                    checkpoint = None
            else:
                console.print("[dim]No existing datasets to snapshot[/dim]")

        # Initialize safety guard
        from tengil.core.safety import get_safety_guard
        safety = get_safety_guard(mock=dry_run)

        # Initialize state tracking
        state = StateStore()

        # Initialize permission manager (unified permission handling)
        permission_mgr = PermissionManager()

        # Initialize managers (pass permission_mgr for unified permission handling)
        zfs = ZFSManager(mock=dry_run, state_store=state, permission_manager=permission_mgr)
        proxmox = ProxmoxManager(mock=dry_run, permission_manager=permission_mgr)
        nas = NASManager(mock=dry_run, permission_manager=permission_mgr)

        # Apply changes using ChangeApplicator
        applicator = ChangeApplicator(zfs, proxmox, nas, state, console)
        applicator.apply_changes(changes, all_desired)

        # Show state summary
        stats = state.get_stats()
        console.print("\n[cyan]State Summary:[/cyan]")
        console.print(f"  Datasets managed: {stats['datasets_managed']}")
        console.print(f"    Created by Tengil: {stats['datasets_created']}")
        console.print(f"    Pre-existing: {stats['datasets_external']}")
        console.print(f"  Containers managed: {stats.get('containers_managed', 0)}")
        if stats.get('containers_created', 0) > 0:
            console.print(f"    Created by Tengil: {stats['containers_created']}")
        console.print(f"  Container mounts: {stats['mounts_managed']}")
        console.print(f"  SMB shares: {stats['smb_shares']}")
        console.print(f"  NFS exports: {stats['nfs_shares']}")
        console.print(f"\n[dim]State saved to: {state.state_file}[/dim]")

        console.print("\n[green]✓[/green] Apply complete")

        if checkpoint and not no_checkpoint:
            console.print(f"\n[dim]Recovery checkpoint available from {checkpoint['timestamp']}[/dim]")
            console.print(f"[dim]Use 'tg rollback --to {checkpoint['timestamp']}' if needed[/dim]")

    except Exception as e:
        console.print(f"\n[red]✗ Apply failed:[/red] {e}")

        # Attempt automatic rollback if checkpoint exists
        if checkpoint and recovery and not no_checkpoint:
            console.print("\n[yellow]⚠ Attempting automatic rollback to checkpoint...[/yellow]")
            try:
                if recovery.rollback(checkpoint, force=True):
                    console.print("[green]✓ Rollback successful[/green]")
                    console.print("[yellow]Infrastructure restored to pre-apply state[/yellow]")
                else:
                    console.print("[red]✗ Rollback completed with errors[/red]")
                    console.print("[yellow]⚠ Manual intervention may be required[/yellow]")
                    console.print(f"[dim]Check logs at: {log_file or '/var/log/tengil/tengil.log'}[/dim]")
            except Exception as rollback_error:
                console.print(f"[red]✗ Rollback failed:[/red] {rollback_error}")
                console.print("[yellow]⚠ Manual recovery required[/yellow]")
                console.print("\n[cyan]Manual recovery steps:[/cyan]")
                console.print("  1. Check ZFS snapshots: zfs list -t snapshot")
                console.print(f"  2. Rollback manually: zfs rollback <dataset>@tengil-pre-apply-*")
                console.print("  3. Check backups: ls /var/lib/tengil/backups/")
        else:
            console.print("[yellow]No checkpoint available for automatic rollback[/yellow]")
            if verbose:
                console.print_exception()

        raise typer.Exit(1)

@app.command()
def add(
    app_name: str = typer.Argument(..., help="App to add (e.g., jellyfin, pihole, nextcloud)"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    pool: Optional[str] = typer.Option(None, "--pool", "-p", help="Pool to use (auto-detect if not specified)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Add an app to existing config (e.g., 'tg add jellyfin').
    
    This command makes it easy to add common apps to your existing tengil.yml.
    It will create an optimized dataset, configure the container, and optionally
    set up shares - all with best practices built-in.
    
    Examples:
        tg add jellyfin          # Add Jellyfin media server
        tg add pihole            # Add Pi-hole DNS blocker
        tg add nextcloud -p tank # Add Nextcloud to specific pool
    """
    console.print(f"[yellow]⚠[/yellow]  The 'add' command is coming soon!")
    console.print(f"\nFor now, use:")
    console.print(f"  [cyan]tg init --package {app_name}[/cyan]  # Start fresh config")
    console.print(f"\nOr manually edit tengil.yml to add {app_name}")
    console.print(f"\n💡 This feature will let you add apps to existing configs seamlessly.")
    raise typer.Exit(0)

@app.command()
def init(
    template: Optional[str] = typer.Option(None, "--template", "-t", 
                                          help="Template name (e.g., homelab, media-server)"),
    templates: Optional[str] = typer.Option(None, "--templates",
                                           help="Comma-separated templates to combine"),
    datasets: Optional[str] = typer.Option(None, "--datasets", 
                                          help="Comma-separated dataset names to include"),
    package: Optional[str] = typer.Option(None, "--package", "-P",
                                         help="Package name (e.g., media-server, nas-complete)"),
    pool: str = typer.Option("tank", "--pool", "-p", help="ZFS pool name"),
    list_templates: bool = typer.Option(False, "--list-templates", help="List available templates"),
    list_datasets: bool = typer.Option(False, "--list-datasets", help="List available datasets"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Skip prompts, use defaults")
):
    """Initialize a new tengil.yml from a preset package.
    
    This is the fastest way to get started. Choose a package that matches
    your use case, and Tengil generates an optimized configuration.
    
    Examples:
        tg init --template homelab                  # Use homelab template
        tg init --templates homelab,media-server    # Combine multiple templates
        tg init --datasets movies,tv,photos         # Select specific datasets
        tg init --package media-server              # Use preset package (interactive)
        tg init --package nas-complete --non-interactive  # Use package with defaults
    """
    # List available options
    if list_templates:
        available = template_loader.list_templates()
        console.print("[cyan]Available templates:[/cyan]\n")
        for t in available:
            desc = template_loader.get_template_info(t)
            console.print(f"  [bold]{t}[/bold]")
            console.print(f"    {desc}\n")
        return
    
    if list_datasets:
        available = template_loader.list_datasets()
        console.print("[cyan]Available datasets:[/cyan]\n")
        for d in available:
            desc, _ = template_loader.get_dataset_info(d)
            console.print(f"  [bold]{d}[/bold]")
            console.print(f"    {desc}\n")
        return
    
    # Check for existing config
    config_path = Path.home() / "tengil-configs" / "tengil.yml"
    if config_path.exists():
        console.print("[yellow]Warning:[/yellow] tengil.yml already exists")
        if not typer.confirm("Overwrite?"):
            return
    
    try:
        configs_to_merge = []
        
        # Load from --package flag (preset packages)
        if package:
            console.print(f"[cyan]Loading package:[/cyan] {package}\n")
            
            package_loader = PackageLoader()
            pkg = package_loader.load_package(package)
            
            # Show package info
            console.print(f"[bold]{pkg.name}[/bold]")
            console.print(f"{pkg.description}\n")
            
            if pkg.components:
                console.print("[dim]Components:[/dim]")
                for comp in pkg.components:
                    console.print(f"  • {comp}")
                console.print()
            
            # Collect user inputs
            user_inputs = {"pool_name": pool}  # Default pool name
            
            if pkg.prompts and not non_interactive:
                console.print("[bold]Customization:[/bold]")
                for prompt in pkg.prompts:
                    # Show prompt with default
                    default_display = f" [{prompt.default}]" if prompt.default is not None else ""
                    user_input = typer.prompt(
                        f"  {prompt.prompt}{default_display}",
                        default=prompt.default if prompt.default is not None else "",
                        show_default=False
                    )
                    
                    # Type conversion
                    if prompt.type == "int":
                        user_inputs[prompt.id] = int(user_input) if user_input else prompt.default
                    elif prompt.type == "bool":
                        # Handle empty input (use default) and string conversion
                        if user_input == "" or user_input is None:
                            user_inputs[prompt.id] = prompt.default
                        elif isinstance(user_input, bool):
                            user_inputs[prompt.id] = user_input
                        else:
                            user_inputs[prompt.id] = str(user_input).lower() in ['true', 'yes', 'y', '1']
                    else:
                        user_inputs[prompt.id] = user_input if user_input else prompt.default
                
                console.print()
            elif pkg.prompts and non_interactive:
                # Use defaults for all prompts
                console.print("[dim]Using default values for all prompts[/dim]\n")
                for prompt in pkg.prompts:
                    user_inputs[prompt.id] = prompt.default
            
            # Check if this is a Docker Compose package
            if pkg.docker_compose:
                console.print("[cyan]📦 Docker Compose integration detected[/cyan]")
                console.print(f"[dim]Analyzing compose file...[/dim]\n")
                
                # Generate config from Docker Compose
                final_config = package_loader.render_compose_config(pkg, user_inputs)
                
                console.print("[green]✓[/green] Generated config from Docker Compose + Tengil opinions")
                console.print(f"[dim]  Datasets: {len(final_config['pools'][pool]['datasets'])}[/dim]")
            else:
                # Traditional package with embedded config
                # Render package config with user inputs
                final_config = package_loader.render_config(pkg, user_inputs)
        
        # Load from --datasets flag
        elif datasets:
            dataset_list = [d.strip() for d in datasets.split(',')]
            console.print(f"[cyan]Loading datasets:[/cyan] {', '.join(dataset_list)}")
            # Create a config structure with dataset references
            configs_to_merge.append({
                "datasets": dataset_list
            })
        
        # Load from --templates flag (multiple)
        elif templates:
            template_list = [t.strip() for t in templates.split(',')]
            console.print(f"[cyan]Loading templates:[/cyan] {', '.join(template_list)}")
            for template_name in template_list:
                template_config = template_loader.load_template(template_name)
                configs_to_merge.append(template_config)
        
        # Load from --template flag (single, backward compatible)
        elif template:
            console.print(f"[cyan]Loading template:[/cyan] {template}")
            template_config = template_loader.load_template(template)
            configs_to_merge.append(template_config)
        
        # Default to homelab template
        else:
            console.print("[cyan]Loading default template:[/cyan] homelab")
            template_config = template_loader.load_template("homelab")
            configs_to_merge.append(template_config)
        
        # Process non-package configs
        if not package:
            # Merge all configurations
            merged_config = template_loader.merge_configs(configs_to_merge)
            
            # Substitute ${pool} variable
            final_config = template_loader.substitute_pool(merged_config, pool)
        
        # Write configuration
        with open(config_path, 'w') as f:
            yaml.dump(final_config, f, default_flow_style=False, sort_keys=False)
        
        console.print(f"[green]✓[/green] Created {config_path}")
        console.print(f"\n[cyan]Next steps:[/cyan]")
        console.print("  1. Edit tengil.yml to customize your setup")
        console.print("  2. Run 'tg diff' to see what changes will be made")
        console.print("  3. Run 'tg apply' to apply the configuration")
        
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        if package:
            console.print("\n[dim]Use 'tg packages list' to see available packages[/dim]")
        else:
            console.print("\nAvailable templates:")
            for t in template_loader.list_templates():
                console.print(f"  • {t}")
            console.print("\nAvailable datasets:")
            for d in template_loader.list_datasets():
                console.print(f"  • {d}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

@app.command(name="import")
def import_config(
    pool: str = typer.Argument(..., help="ZFS pool to scan"),
    output: str = typer.Option("tengil-imported.yml", "--output", "-o", 
                               help="Output file path"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", 
                                 help="Show what would be imported without writing")
):
    """Import existing ZFS/Proxmox infrastructure into tengil.yml.
    
    Scans your existing ZFS datasets and Proxmox container mounts,
    then generates a tengil.yml configuration file.
    
    Example:
        tg import tank --output tengil.yml
    """
    console.print("[bold cyan]Tengil Import[/bold cyan]")
    console.print(f"Scanning pool: [yellow]{pool}[/yellow]\n")
    
    mock = os.environ.get('TG_MOCK') == '1' or dry_run
    importer = InfrastructureImporter(mock=mock)
    
    # Generate configuration
    config = importer.generate_config(pool)
    
    # Show summary
    console.print(f"[green]✓[/green] Found {len(config['datasets'])} dataset(s)")
    for name, dataset in config['datasets'].items():
        console.print(f"  • {name} ({dataset['profile']})")
        if 'containers' in dataset:
            for ct in dataset['containers']:
                console.print(f"    → {ct['name']}: {ct['mount']}")
    
    if dry_run:
        console.print(f"\n[yellow]Dry run - would write to:[/yellow] {output}")
        console.print("\n[dim]Generated config:[/dim]")
        console.print(yaml.dump(config, default_flow_style=False))
    else:
        output_path = Path(output)
        if importer.write_config(config, output_path):
            console.print(f"\n[green]✓ Wrote configuration to:[/green] {output}")
            console.print("\n[yellow]Next steps:[/yellow]")
            console.print(f"  1. Review: cat {output}")
            console.print("  2. Edit profiles and add any missing containers")
            console.print(f"  3. Apply: tg apply --config {output}")
        else:
            console.print("[red]Failed to write configuration[/red]")
            raise typer.Exit(1)

@app.command()
def snapshot(
    name: str = typer.Option(None, "--name", help="Snapshot name"),
    list_snapshots: bool = typer.Option(False, "--list", "-l", help="List snapshots"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Clean up old snapshots"),
    keep: int = typer.Option(5, help="Number of snapshots to keep")
):
    """Manage ZFS snapshots for rollback."""
    snapshot_manager = SnapshotManager(mock=is_mock())

    if list_snapshots:
        snapshots = snapshot_manager.list_snapshots()
        if not snapshots:
            console.print("[yellow]No tengil snapshots found[/yellow]")
            return

        from rich.table import Table
        table = Table(title="Tengil Snapshots")
        table.add_column("Dataset", style="cyan")
        table.add_column("Snapshot", style="green")
        table.add_column("Created", style="yellow")
        table.add_column("Size", style="magenta")

        for snap in snapshots:
            table.add_row(
                snap['dataset'],
                snap['name'],
                snap['created'],
                snap['used']
            )

        console.print(table)

    elif cleanup:
        deleted = snapshot_manager.cleanup_old_snapshots(keep=keep)
        console.print(f"[green]Deleted {deleted} old snapshot(s)[/green]")

    else:
        # Create snapshot of all managed datasets
        state = StateStore()
        datasets = list(state.state.get('datasets', {}).keys())

        if not datasets:
            console.print("[yellow]No managed datasets found[/yellow]")
            return

        created = snapshot_manager.create_snapshot(datasets, name=name)
        console.print(f"[green]Created {len(created)} snapshot(s)[/green]")
        for dataset, snap_name in created.items():
            console.print(f"  {dataset}@{snap_name}")

@app.command()
def rollback(
    dataset: str = typer.Argument(..., help="Dataset to rollback"),
    to: str = typer.Option(..., "--to", help="Snapshot name to rollback to"),
    force: bool = typer.Option(False, "--force", help="Force rollback (destroys newer snapshots)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Rollback dataset to snapshot (like 'terraform destroy', but safer)."""
    """Rollback dataset to previous snapshot."""
    snapshot_manager = SnapshotManager(mock=is_mock())

    # Confirm unless --yes or mock mode
    if not yes and not is_mock():
        console.print(f"[yellow]⚠️  Rollback {dataset} to {to}?[/yellow]")
        console.print("[yellow]This will destroy all changes after this snapshot.[/yellow]")
        if not typer.confirm("Continue?"):
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    if snapshot_manager.rollback(dataset, to, force=force):
        console.print(f"[green]✓ Rolled back {dataset} to {to}[/green]")
    else:
        console.print(f"[red]✗ Failed to rollback {dataset}[/red]")
        raise typer.Exit(1)

@app.command()
def suggest(
    dataset_type: Optional[str] = typer.Argument(None, help="Dataset type (media, photos, backups, etc.)")
):
    """Suggest LXC containers for dataset types.
    
    Examples:
        tg suggest              # Show all recommendations
        tg suggest media        # Show media server options
        tg suggest photos       # Show photo management options
    """
    if dataset_type:
        if not show_dataset_recommendations(dataset_type, console):
            raise typer.Exit(1)
    else:
        show_all_recommendations(console)


# Docker Discovery Helper Functions

def _show_docker_containers(discovery, show_all: bool, console: Console):
    """Show Docker containers in a table."""
    from rich.table import Table
    
    containers = discovery.list_containers(all=show_all)
    
    if not containers:
        console.print("[yellow]No containers found[/yellow]")
        return
    
    table = Table(title="Docker Containers", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Image", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Ports")
    
    for container in containers:
        status_style = "green" if container.status == "running" else "yellow"
        ports_str = ", ".join(container.ports[:2]) if container.ports else "-"
        if len(container.ports) > 2:
            ports_str += f" +{len(container.ports)-2}"
        
        table.add_row(
            container.id[:12],
            container.name,
            container.image,
            f"[{status_style}]{container.status}[/{status_style}]",
            ports_str
        )
    
    console.print(table)
    console.print(f"\n[dim]Found {len(containers)} container(s)[/dim]")


def _show_docker_images(discovery, console: Console):
    """Show Docker images in a table."""
    from rich.table import Table
    
    images = discovery.list_images()
    
    if not images:
        console.print("[yellow]No images found[/yellow]")
        return
    
    table = Table(title="Docker Images", show_header=True)
    table.add_column("Repository", style="bold")
    table.add_column("Tag", style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Size")
    table.add_column("Created")
    
    for image in images:
        table.add_row(
            image.repository,
            image.tag,
            image.id[:12],
            image.size,
            image.created
        )
    
    console.print(table)
    console.print(f"\n[dim]Found {len(images)} image(s)[/dim]")


def _show_docker_compose_stacks(discovery, console: Console):
    """Show Docker Compose stacks."""
    from rich.table import Table
    
    stacks = discovery.list_compose_stacks()
    
    if not stacks:
        console.print("[yellow]No Compose stacks found[/yellow]")
        console.print("[dim]Only containers with com.docker.compose.project label are detected[/dim]")
        return
    
    table = Table(title="Docker Compose Stacks", show_header=True)
    table.add_column("Project", style="bold cyan")
    table.add_column("Services", style="blue")
    table.add_column("Containers", style="green")
    
    for stack in stacks:
        table.add_row(
            stack.project,
            str(len(stack.services)),
            ", ".join(stack.containers[:3]) + (f" +{len(stack.containers)-3}" if len(stack.containers) > 3 else "")
        )
    
    console.print(table)
    console.print(f"\n[dim]Found {len(stacks)} stack(s)[/dim]")


def _handle_docker_search(discovery, pattern: str, console: Console):
    """Search Docker containers by name or image."""
    matches = discovery.search_containers(pattern)
    
    if not matches:
        console.print(f"[yellow]No containers found matching '{pattern}'[/yellow]")
        return
    
    console.print(f"\n[cyan]Containers matching '{pattern}':[/cyan]")
    for container in matches:
        status_style = "green" if container.status == "running" else "yellow"
        console.print(f"  [{status_style}]●[/{status_style}] {container.name} ({container.image})")
        console.print(f"     ID: {container.id} - Status: [{status_style}]{container.status}[/{status_style}]")


def _handle_compose_reverse(discovery, container_id: str, console: Console):
    """Reverse-engineer Docker Compose from running container."""
    import yaml
    from pathlib import Path
    
    console.print(f"\n[cyan]Reverse-engineering compose for container: {container_id}[/cyan]\n")
    
    compose = discovery.reverse_engineer_compose(container_id)
    
    if not compose:
        console.print(f"[red]Container not found: {container_id}[/red]")
        return
    
    # Display generated compose
    compose_yaml = yaml.dump(compose, default_flow_style=False, sort_keys=False)
    console.print("[bold]Generated Docker Compose:[/bold]")
    console.print(f"[dim]{'-' * 60}[/dim]")
    console.print(compose_yaml)
    console.print(f"[dim]{'-' * 60}[/dim]")
    
    # Ask to save to cache
    from rich.prompt import Confirm, Prompt
    
    if Confirm.ask("\nSave to compose_cache?", default=False):
        service_name = list(compose['services'].keys())[0]
        default_name = service_name.replace('_', '-').lower()
        
        app_name = Prompt.ask("App name for cache", default=default_name)
        
        cache_dir = Path.cwd() / "compose_cache" / app_name
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        compose_file = cache_dir / "docker-compose.yml"
        compose_file.write_text(compose_yaml)
        
        # Create version.txt
        version_file = cache_dir / "version.txt"
        version_content = f"""source: reverse-engineered
container_id: {container_id}
curated: {Path(__file__).stat().st_mtime}
notes: |
  Reverse-engineered from running container.
  Review and adjust as needed.
"""
        version_file.write_text(version_content)
        
        console.print(f"\n[green]✓ Saved to: {cache_dir}/[/green]")
        console.print(f"[dim]  - docker-compose.yml[/dim]")
        console.print(f"[dim]  - version.txt[/dim]")
        console.print(f"\n[yellow]⚠ Review the generated compose and add README.md with notes[/yellow]")


def _show_docker_overview(discovery, console: Console):
    """Show Docker overview (containers + images + stacks)."""
    console.print("\n[cyan bold]Docker Discovery Overview[/cyan bold]\n")
    
    # Containers
    containers = discovery.list_containers(all=False)
    console.print(f"[cyan]Running Containers:[/cyan] {len(containers)}")
    for c in containers[:3]:
        console.print(f"  ● {c.name} ({c.image})")
    if len(containers) > 3:
        console.print(f"  [dim]... and {len(containers) - 3} more[/dim]")
    
    # Images
    images = discovery.list_images()
    console.print(f"\n[cyan]Local Images:[/cyan] {len(images)}")
    for img in images[:3]:
        console.print(f"  • {img.repository}:{img.tag}")
    if len(images) > 3:
        console.print(f"  [dim]... and {len(images) - 3} more[/dim]")
    
    # Compose stacks
    stacks = discovery.list_compose_stacks()
    if stacks:
        console.print(f"\n[cyan]Compose Stacks:[/cyan] {len(stacks)}")
        for stack in stacks[:3]:
            console.print(f"  📦 {stack.project} ({len(stack.services)} services)")
        if len(stacks) > 3:
            console.print(f"  [dim]... and {len(stacks) - 3} more[/dim]")
    
    console.print(f"\n[dim]Run with --docker-containers, --docker-images, or --docker-compose for details[/dim]")


@app.command()
def discover(
    # LXC/Proxmox options
    host: Optional[str] = typer.Option(None, "--host", "-h", help="Proxmox host (IP or hostname)"),
    user: str = typer.Option("root", "--user", "-u", help="SSH user"),
    templates: bool = typer.Option(False, "--templates", "-t", help="Show available LXC templates"),
    containers: bool = typer.Option(False, "--containers", "-c", help="Show existing LXC containers"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search for LXC template"),
    # Docker discovery options
    docker_containers: bool = typer.Option(False, "--docker-containers", help="Show Docker containers"),
    docker_images: bool = typer.Option(False, "--docker-images", help="Show Docker images"),
    docker_compose: bool = typer.Option(False, "--docker-compose", help="Show Docker Compose stacks"),
    docker_search: Optional[str] = typer.Option(None, "--docker-search", help="Search Docker containers/images"),
    compose_reverse: Optional[str] = typer.Option(None, "--compose-reverse", help="Reverse-engineer compose from container"),
    docker_host: Optional[str] = typer.Option(None, "--docker-host", help="Docker host URL (tcp://host:2375, ssh://user@host)"),
    docker_context: Optional[str] = typer.Option(None, "--docker-context", help="Docker context to use"),
    all_containers: bool = typer.Option(False, "--all", "-a", help="Include stopped containers (for Docker)")
):
    """Discover LXC templates, Docker containers, images, and Compose stacks.
    
    LXC/Proxmox Discovery:
        tg discover --containers                    # List LXC containers
        tg discover --templates                     # List LXC templates
        tg discover --search jellyfin               # Search LXC templates
        tg discover --host 192.168.1.42 --templates # Remote Proxmox
    
    Docker Discovery:
        tg discover --docker-containers             # List running containers
        tg discover --docker-containers --all       # Include stopped
        tg discover --docker-images                 # List local images
        tg discover --docker-compose                # List Compose stacks
        tg discover --docker-search jellyfin        # Search containers
        tg discover --compose-reverse abc123        # Generate compose from container
    
    Remote Docker:
        tg discover --docker-containers --docker-host tcp://192.168.1.42:2375
        tg discover --docker-containers --docker-context production
    """
    
    # Determine if user wants Docker or LXC discovery
    docker_mode = any([
        docker_containers, docker_images, docker_compose, 
        docker_search is not None, compose_reverse is not None
    ])
    
    if docker_mode:
        # Docker Discovery
        from tengil.discovery.docker_discovery import DockerDiscovery
        
        try:
            discovery = DockerDiscovery(host=docker_host, context=docker_context)
        except Exception as e:
            console.print(f"[red]Error connecting to Docker: {e}[/red]")
            console.print("[yellow]Make sure Docker is running and accessible[/yellow]")
            raise typer.Exit(1)
        
        # Handle compose reverse engineering
        if compose_reverse:
            _handle_compose_reverse(discovery, compose_reverse, console)
            return
        
        # Handle Docker search
        if docker_search:
            _handle_docker_search(discovery, docker_search, console)
            return
        
        # Handle specific Docker discovery modes
        if docker_containers:
            _show_docker_containers(discovery, all_containers, console)
            return
        
        if docker_images:
            _show_docker_images(discovery, console)
            return
        
        if docker_compose:
            _show_docker_compose_stacks(discovery, console)
            return
        
        # Default: show overview
        _show_docker_overview(discovery, console)
        return
    
    # Original LXC/Proxmox discovery code
    discovery = ProxmoxDiscovery(host=host, user=user)
    
    if search:
        # Search for templates
        results = discovery.search_template(search)
        if results:
            console.print(f"\n[cyan]Templates matching '{search}':[/cyan]")
            for t in results:
                template_type = t.get('type', 'unknown')
                console.print(f"  [{template_type}] [bold]{t['name']}[/bold]")
        else:
            console.print(f"[yellow]No templates found matching '{search}'[/yellow]")
        return
    
    if containers:
        # List existing containers
        ctrs = discovery.get_existing_containers()
        if ctrs:
            console.print("\n[cyan]Existing LXC Containers:[/cyan]")
            console.print(f"{'VMID':<8} {'Status':<10} {'Name'}")
            console.print("-" * 50)
            for c in ctrs:
                status_color = "green" if c['status'] == 'running' else "yellow"
                console.print(f"{c['vmid']:<8} [{status_color}]{c['status']:<10}[/{status_color}] {c['name']}")
        else:
            console.print("[yellow]No containers found[/yellow]")
        return
    
    if templates:
        # List available templates
        tmpls = discovery.get_available_templates()
        if tmpls:
            console.print("\n[cyan]Available LXC Templates:[/cyan]")
            console.print(f"[dim]Found {len(tmpls)} templates from Proxmox repository[/dim]\n")
            
            # Group by type
            grouped = {}
            for t in tmpls:
                template_type = t['type']
                if template_type not in grouped:
                    grouped[template_type] = []
                grouped[template_type].append(t)
            
            # Show grouped
            for template_type in sorted(grouped.keys()):
                templates_list = grouped[template_type]
                console.print(f"[bold cyan]{template_type.upper()}:[/bold cyan] {len(templates_list)} templates")
                for t in templates_list[:5]:  # Show first 5 of each type
                    # Extract just the OS name for readability
                    name = t['name']
                    simple_name = name.split('_')[0] if '_' in name else name
                    console.print(f"  {simple_name}")
                if len(templates_list) > 5:
                    console.print(f"  [dim]... and {len(templates_list) - 5} more[/dim]")
                console.print()
            
            console.print(f"[dim]Use --search <name> to find specific templates[/dim]")
            
            # Show downloaded templates separately
            downloaded = discovery.get_downloaded_templates()
            if downloaded:
                console.print(f"\n[green]Downloaded templates:[/green] {len(downloaded)}")
                for t in downloaded:
                    console.print(f"  ✓ {t['name']} ({t['size']})")
        else:
            console.print("[yellow]No templates found. Run 'pveam update' on Proxmox to refresh.[/yellow]")
        return
    
    # Default: show both
    console.print("\n[cyan bold]Proxmox Discovery[/cyan bold]")
    if host:
        console.print(f"[dim]Host: {host}[/dim]\n")
    
    # Containers
    ctrs = discovery.get_existing_containers()
    console.print(f"[cyan]Existing Containers:[/cyan] {len(ctrs)}")
    if ctrs:
        for c in ctrs[:5]:  # Show first 5
            status_color = "green" if c['status'] == 'running' else "yellow"
            console.print(f"  {c['vmid']} - [{status_color}]{c['status']}[/{status_color}] {c['name']}")
        if len(ctrs) > 5:
            console.print(f"  [dim]... and {len(ctrs) - 5} more[/dim]")
    
    # Templates
    tmpls = discovery.get_available_templates()
    console.print(f"\n[cyan]Available Templates:[/cyan] {len(tmpls)}")
    if tmpls:
        for t in tmpls[:5]:  # Show first 5
            console.print(f"  {t['name']} ({t['size']})")
        if len(tmpls) > 5:
            console.print(f"  [dim]... and {len(tmpls) - 5} more[/dim]")
    
    console.print(f"\n[dim]Run with --containers, --templates, or --search for more details[/dim]")

@app.command()
def install(
    dataset_type: str = typer.Argument(..., help="Dataset type (media, photos, ai, etc.)"),
    host: Optional[str] = typer.Option(None, "--host", "-h", help="Proxmox host (IP or hostname)"),
    user: str = typer.Option("root", "--user", "-u", help="SSH user"),
    apps: Optional[str] = typer.Option(None, "--apps", "-a", help="Comma-separated apps to install"),
    script_only: bool = typer.Option(False, "--script-only", help="Generate script without executing")
):
    """Smart container installation with template matching.
    
    Shows available templates for recommended apps and generates install commands.
    
    Examples:
        tg install media --host 192.168.1.42           # Show media app options
        tg install photos --apps immich,photoprism     # Install specific apps
        tg install ai --script-only                    # Generate install script
    """
    discovery = ProxmoxDiscovery(host=host, user=user)
    matcher = SmartContainerMatcher(discovery, console)
    
    if apps:
        # Generate and optionally run install script
        app_list = [a.strip() for a in apps.split(',')]
        script = matcher.generate_install_script(dataset_type, app_list)
        
        if script_only:
            console.print(script)
        else:
            console.print("[yellow]⚠ Automatic installation not yet implemented[/yellow]")
            console.print("[dim]Use --script-only to generate script, then run manually on Proxmox[/dim]")
    else:
        # Show smart suggestions
        matcher.show_smart_suggestions(dataset_type)

@app.command()
def templates(
    update: bool = typer.Option(False, "--update", "-u", help="Update template list first"),
    local: bool = typer.Option(False, "--local", "-l", help="Show only downloaded templates")
):
    """List available LXC templates.
    
    Shows templates available for container creation.
    
    Examples:
        tg templates                  # Show all available templates
        tg templates --local          # Show only downloaded templates
        tg templates --update         # Update and show template list
    """
    from tengil.services.proxmox.containers.templates import TemplateManager
    
    template_mgr = TemplateManager(mock=is_mock())
    
    if local:
        console.print("[bold]Downloaded Templates:[/bold]")
        # List local templates
        try:
            result = subprocess.run(
                ['pveam', 'list', 'local'],
                capture_output=True,
                text=True,
                check=True
            )
            for line in result.stdout.splitlines():
                if 'vztmpl' in line:
                    console.print(f"  • {line.strip()}")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Error listing local templates: {e}[/red]")
    else:
        if update:
            console.print("[dim]Updating template list...[/dim]")
        
        available = template_mgr.list_available_templates()
        
        if available:
            console.print(f"[bold]Available LXC Templates ({len(available)}):[/bold]\n")
            
            # Group by OS
            debian = [t for t in available if 'debian' in t.lower()]
            ubuntu = [t for t in available if 'ubuntu' in t.lower()]
            others = [t for t in available if t not in debian and t not in ubuntu]
            
            if debian:
                console.print("[bold cyan]Debian:[/bold cyan]")
                for tmpl in debian[:10]:
                    console.print(f"  • {tmpl}")
                if len(debian) > 10:
                    console.print(f"  [dim]... and {len(debian) - 10} more[/dim]")
            
            if ubuntu:
                console.print("\n[bold cyan]Ubuntu:[/bold cyan]")
                for tmpl in ubuntu[:10]:
                    console.print(f"  • {tmpl}")
                if len(ubuntu) > 10:
                    console.print(f"  [dim]... and {len(ubuntu) - 10} more[/dim]")
            
            if others:
                console.print("\n[bold cyan]Other:[/bold cyan]")
                for tmpl in others[:10]:
                    console.print(f"  • {tmpl}")
                if len(others) > 10:
                    console.print(f"  [dim]... and {len(others) - 10} more[/dim]")
            
            console.print("\n[dim]Use template name in tengil.yml: template: debian-12-standard[/dim]")
        else:
            console.print("[red]No templates available. Check network connection.[/red]")

@app.command()
def packages(
    action: str = typer.Argument(None, help="Action: list, show, search"),
    query: Optional[str] = typer.Argument(None, help="Package name or search query"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category")
):
    """Browse preset packages - the easiest way to get started.
    
    Packages are pre-configured setups for common homelab scenarios.
    They include optimized storage, apps, and shares - just customize and deploy.
    
    Think: "Docker Hub, but for Proxmox + ZFS infrastructure"
    
    Examples:
        tg packages list                           # Browse all packages
        tg packages list --category media          # Media server packages
        tg packages show media-server              # Details for one package
        tg init --package media-server             # Use a package
    """
    loader = PackageLoader()
    
    if action == "list" or action is None:
        # List all packages (optionally filtered by category)
        packages_list = loader.list_packages(category=category)
        
        if not packages_list:
            if category:
                console.print(f"[yellow]No packages found in category: {category}[/yellow]")
            else:
                console.print("[yellow]No packages found[/yellow]")
            return
        
        # Group by category
        by_category = {}
        for pkg in packages_list:
            if pkg.category not in by_category:
                by_category[pkg.category] = []
            by_category[pkg.category].append(pkg)
        
        console.print("[bold cyan]Available Packages:[/bold cyan]\n")
        
        for cat, pkgs in sorted(by_category.items()):
            console.print(f"[bold yellow]{cat.upper()}[/bold yellow]")
            for pkg in pkgs:
                console.print(f"  [bold]{pkg.slug}[/bold] - {pkg.description}")
                if pkg.components:
                    console.print(f"    [dim]Components: {', '.join(pkg.components[:3])}{'...' if len(pkg.components) > 3 else ''}[/dim]")
            console.print()
        
        console.print(f"[dim]Total: {len(packages_list)} package(s)[/dim]")
        console.print("[dim]Use 'tg packages show <name>' for details[/dim]")
        console.print("[dim]Use 'tg init --package <name>' to install[/dim]")
    
    elif action == "show":
        if not query:
            console.print("[red]Error: Package name required[/red]")
            console.print("Example: tg packages show nas-complete")
            raise typer.Exit(1)
        
        try:
            pkg = loader.load_package(query)
            
            console.print(f"[bold cyan]{pkg.name}[/bold cyan]")
            console.print(f"[dim]{pkg.slug}[/dim]\n")
            console.print(pkg.description)
            console.print()
            
            if pkg.category:
                console.print(f"[bold]Category:[/bold] {pkg.category}")
            
            if pkg.tags:
                console.print(f"[bold]Tags:[/bold] {', '.join(pkg.tags)}")
            
            if pkg.components:
                console.print(f"\n[bold]Components:[/bold]")
                for comp in pkg.components:
                    console.print(f"  • {comp}")
            
            if pkg.requirements:
                console.print(f"\n[bold]System Requirements:[/bold]")
                req = pkg.requirements
                if req.min_ram_mb:
                    console.print(f"  Minimum RAM: {req.min_ram_mb}MB")
                if req.min_disk_gb:
                    console.print(f"  Minimum Disk: {req.min_disk_gb}GB")
                if req.recommended_ram_mb:
                    console.print(f"  Recommended RAM: {req.recommended_ram_mb}MB")
                if req.recommended_cores:
                    console.print(f"  Recommended Cores: {req.recommended_cores}")
            
            if pkg.prompts:
                console.print(f"\n[bold]Customization Options:[/bold]")
                for prompt in pkg.prompts:
                    default_str = f" (default: {prompt.default})" if prompt.default else ""
                    console.print(f"  • {prompt.prompt}{default_str}")
            
            if pkg.related:
                console.print(f"\n[bold]Related Packages:[/bold]")
                for rel in pkg.related:
                    console.print(f"  • {rel}")
            
            if pkg.notes:
                console.print(f"\n[bold]Notes:[/bold]")
                console.print(pkg.notes)
            
            console.print(f"\n[dim]Install with: tg init --package {pkg.slug}[/dim]")
        
        except FileNotFoundError:
            console.print(f"[red]Error: Package not found: {query}[/red]")
            console.print("\n[dim]Use 'tg packages list' to see available packages[/dim]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error loading package: {e}[/red]")
            raise typer.Exit(1)
    
    elif action == "search":
        if not query:
            console.print("[red]Error: Search query required[/red]")
            console.print("Example: tg packages search media")
            raise typer.Exit(1)
        
        results = loader.search_packages(query)
        
        if not results:
            console.print(f"[yellow]No packages found matching: {query}[/yellow]")
            return
        
        console.print(f"[bold cyan]Search Results ({len(results)}):[/bold cyan]\n")
        
        for pkg in results:
            console.print(f"  [bold]{pkg.slug}[/bold] ({pkg.category})")
            console.print(f"    {pkg.description}")
            if pkg.tags:
                console.print(f"    [dim]Tags: {', '.join(pkg.tags)}[/dim]")
            console.print()
        
        console.print("[dim]Use 'tg packages show <name>' for details[/dim]")
    
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("[dim]Valid actions: list, show, search[/dim]")
        raise typer.Exit(1)


@app.command()
def doctor(
    save: bool = typer.Option(False, "--save", help="Save system info to ~/.tengil/system.json"),
):
    """Show system hardware and software information.
    
    Detects CPU, GPU, memory, storage, network, and OS details.
    Useful for troubleshooting and understanding what Tengil can work with.
    """
    from tengil.discovery.hwdetect import SystemDetector
    from rich.table import Table
    from rich.panel import Panel
    
    console.print("\n[bold cyan]🔍 System Detection[/bold cyan]\n")
    
    detector = SystemDetector()
    facts = detector.detect_all()
    
    # CPU Info
    cpu = facts['cpu']
    console.print(Panel(
        f"[bold]Model:[/bold] {cpu['model']}\n"
        f"[bold]Cores:[/bold] {cpu['cores']}\n"
        f"[bold]Threads:[/bold] {cpu['threads']}",
        title="💻 CPU",
        border_style="blue"
    ))
    
    # GPU Info
    gpus = facts['gpu']
    if gpus:
        gpu_info = "\n".join([
            f"[bold]{gpu['type'].upper()}:[/bold] {gpu['model']}" + 
            (f" (Driver: {gpu['driver']})" if 'driver' in gpu else "")
            for gpu in gpus
        ])
        console.print(Panel(
            gpu_info,
            title="🎮 GPU",
            border_style="green"
        ))
    else:
        console.print(Panel(
            "[dim]No GPU detected[/dim]",
            title="🎮 GPU",
            border_style="yellow"
        ))
    
    # Memory Info
    memory = facts['memory']
    console.print(Panel(
        f"[bold]Total:[/bold] {memory['total_gb']} GB",
        title="🧠 Memory",
        border_style="magenta"
    ))
    
    # Storage Info
    storage = facts['storage']
    if storage:
        table = Table(title="💾 ZFS Pools", show_header=True)
        table.add_column("Pool", style="cyan")
        table.add_column("Size", style="blue")
        table.add_column("Allocated", style="yellow")
        table.add_column("Free", style="green")
        table.add_column("Health", style="bold")
        
        for pool in storage:
            health_color = "green" if pool['health'] == 'ONLINE' else "red"
            table.add_row(
                pool['name'],
                pool['size'],
                pool['alloc'],
                pool['free'],
                f"[{health_color}]{pool['health']}[/{health_color}]"
            )
        
        console.print(table)
    else:
        console.print(Panel(
            "[dim]No ZFS pools detected[/dim]",
            title="💾 Storage",
            border_style="yellow"
        ))
    
    # Network Info
    network = facts['network']
    if network:
        net_info = "\n".join([
            f"[bold]{iface['name']}:[/bold] " + 
            ("[green]UP[/green]" if iface['up'] else "[red]DOWN[/red]")
            for iface in network
        ])
        console.print(Panel(
            net_info,
            title="🌐 Network",
            border_style="cyan"
        ))
    
    # OS Info
    os_info = facts['os']
    console.print(Panel(
        f"[bold]OS:[/bold] {os_info['name']}\n"
        f"[bold]Kernel:[/bold] {os_info['kernel']}",
        title="🐧 Operating System",
        border_style="blue"
    ))
    
    # Save if requested
    if save:
        path = detector.save_state()
        console.print(f"\n[green]✓[/green] System info saved to: {path}")
    else:
        console.print(f"\n[dim]Tip: Use --save to store this info in ~/.tengil/system.json[/dim]")
    
    console.print()


# ============================================================================
# COMPOSE COMMANDS - Docker Compose integration tools
# ============================================================================

compose_app = typer.Typer(help="Docker Compose integration tools")
app.add_typer(compose_app, name="compose")


@compose_app.command("analyze")
def compose_analyze(
    file: str = typer.Argument(..., help="Path or URL to docker-compose.yml"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, yaml"),
    show_secrets: bool = typer.Option(False, "--secrets", help="Show extracted secrets"),
    show_volumes: bool = typer.Option(True, "--volumes", help="Show volume mounts"),
    show_ports: bool = typer.Option(False, "--ports", help="Show port mappings"),
):
    """
    Analyze a Docker Compose file and extract infrastructure requirements.

    Examples:
      tg compose analyze ./docker-compose.yml
      tg compose analyze https://raw.githubusercontent.com/.../compose.yml
      tg compose analyze romm.yml --format json
    """
    from tengil.services.docker_compose.analyzer import ComposeAnalyzer
    from rich.table import Table
    from rich.panel import Panel
    import json

    try:
        console.print(f"[dim]Analyzing compose file:[/dim] {file}")
        console.print()

        analyzer = ComposeAnalyzer()
        requirements = analyzer.analyze(file)

        if format == "json":
            output = analyzer.analyze_to_dict(file)
            console.print(json.dumps(output, indent=2))
            return

        elif format == "yaml":
            output = analyzer.analyze_to_dict(file)
            console.print(yaml.dump(output, default_flow_style=False, sort_keys=False))
            return

        # Table format (default)
        console.print(Panel(
            f"[bold]Services:[/bold] {', '.join(requirements.services)}",
            title="📦 Compose Analysis",
            border_style="blue"
        ))

        if show_volumes and requirements.volumes:
            console.print("\n[bold cyan]📁 Volume Mounts (Host Paths)[/bold cyan]")
            vol_table = Table(show_header=True, header_style="bold")
            vol_table.add_column("Host Path", style="yellow")
            vol_table.add_column("Container Path", style="cyan")
            vol_table.add_column("Service", style="green")
            vol_table.add_column("Access", style="dim")

            for vol in requirements.volumes:
                access = "ro" if vol.readonly else "rw"
                vol_table.add_row(vol.host, vol.container, vol.service, access)

            console.print(vol_table)
            console.print()

            # Show unique host paths for dataset creation
            host_paths = requirements.get_host_paths()
            console.print(f"[dim]→ {len(host_paths)} unique host paths need ZFS datasets[/dim]")
            console.print()

        if show_secrets and requirements.secrets:
            console.print("[bold cyan]🔐 Secrets (Empty Environment Variables)[/bold cyan]")
            secrets_table = Table(show_header=True, header_style="bold")
            secrets_table.add_column("Environment Variable", style="yellow")
            secrets_table.add_column("Note", style="dim")

            for secret in sorted(requirements.secrets):
                note = "Needs value" if not secret.endswith("_KEY") else "Generate key"
                secrets_table.add_row(secret, note)

            console.print(secrets_table)
            console.print()

            console.print(f"[dim]→ {len(requirements.secrets)} secrets need to be filled[/dim]")
            console.print()

        if show_ports and requirements.ports:
            console.print("[bold cyan]🌐 Port Mappings[/bold cyan]")
            ports_table = Table(show_header=True, header_style="bold")
            ports_table.add_column("Mapping", style="cyan")

            for port in requirements.ports:
                ports_table.add_row(port)

            console.print(ports_table)
            console.print()

        # Summary
        console.print("[bold green]✓[/bold green] Analysis complete")
        console.print(f"  [dim]• Services:[/dim] {len(requirements.services)}")
        console.print(f"  [dim]• Volumes:[/dim] {len(requirements.volumes)}")
        console.print(f"  [dim]• Secrets:[/dim] {len(requirements.secrets)}")
        console.print(f"  [dim]• Ports:[/dim] {len(requirements.ports)}")

    except FileNotFoundError as e:
        console.print(f"[red]✗ File not found:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗ Analysis failed:[/red] {e}")
        if logger:
            logger.exception("Compose analysis failed")
        raise typer.Exit(1)


@compose_app.command("validate")
def compose_validate(
    file: str = typer.Argument(..., help="Path or URL to docker-compose.yml"),
    check_images: bool = typer.Option(False, "--check-images", help="Verify images exist on Docker Hub"),
):
    """
    Validate a Docker Compose file for Tengil compatibility.

    Checks:
    - Valid YAML syntax
    - Has services section
    - Volume paths are absolute
    - No conflicting port mappings
    """
    from tengil.services.docker_compose.analyzer import ComposeAnalyzer
    from rich.panel import Panel

    try:
        console.print(f"[dim]Validating:[/dim] {file}")
        console.print()

        analyzer = ComposeAnalyzer()
        requirements = analyzer.analyze(file)

        issues = []
        warnings = []

        # Check 1: Services exist
        if not requirements.services:
            issues.append("No services found in compose file")
        else:
            console.print(f"[green]✓[/green] Found {len(requirements.services)} services")

        # Check 2: Volume paths are absolute
        for vol in requirements.volumes:
            if not vol.host.startswith('/'):
                issues.append(f"Non-absolute volume path: {vol.host}")

        if not any(v.host.startswith('/') and not v.host.startswith('/') for v in requirements.volumes):
            console.print(f"[green]✓[/green] All volume paths are absolute")

        # Check 3: Secrets identified
        if requirements.secrets:
            console.print(f"[yellow]⚠[/yellow] {len(requirements.secrets)} secrets need values")
            warnings.append(f"{len(requirements.secrets)} environment variables are empty")

        # Show results
        console.print()

        if issues:
            console.print(Panel(
                "\n".join(f"• {issue}" for issue in issues),
                title="[red]❌ Validation Issues[/red]",
                border_style="red"
            ))
            raise typer.Exit(1)

        if warnings:
            console.print(Panel(
                "\n".join(f"• {warning}" for warning in warnings),
                title="[yellow]⚠️  Warnings[/yellow]",
                border_style="yellow"
            ))

        console.print(Panel(
            "[bold green]✓ Compose file is valid and compatible with Tengil[/bold green]",
            border_style="green"
        ))

    except Exception as e:
        console.print(f"[red]✗ Validation failed:[/red] {e}")
        raise typer.Exit(1)


@compose_app.command("resolve")
def compose_resolve(
    package: str = typer.Argument(..., help="Package name or path to package.yml"),
    show_content: bool = typer.Option(False, "--show-content", help="Show resolved compose content"),
):
    """
    Test compose resolution for a package (cache → source → image → dockerfile).

    Shows which strategy succeeded and the resolved compose metadata.
    """
    from tengil.services.docker_compose.resolver import ComposeResolver
    from tengil.core.package_loader import PackageLoader
    from rich.panel import Panel
    import json

    try:
        # Load package
        loader = PackageLoader()
        if package.endswith('.yml'):
            pkg = loader.load_package_file(Path(package))
        else:
            pkg = loader.load_package(package)

        console.print(f"[dim]Package:[/dim] {pkg.name}")
        console.print(f"[dim]Resolving compose source...[/dim]")
        console.print()

        if not pkg.docker_compose:
            console.print("[red]✗ Package has no docker_compose section[/red]")
            raise typer.Exit(1)

        # Resolve compose
        resolver = ComposeResolver()
        result = resolver.resolve(pkg.docker_compose)

        # Show result
        console.print(Panel(
            f"[bold]Strategy:[/bold] {result.source_type}\n"
            f"[bold]Source:[/bold] {result.source_path}\n"
            f"[bold]Cached:[/bold] {result.metadata.get('cached', False)}\n"
            f"[bold]Verified:[/bold] {result.metadata.get('verified', False)}",
            title="[green]✓ Resolution Successful[/green]",
            border_style="green"
        ))

        # Show compose metadata
        services = list(result.content.get('services', {}).keys())
        console.print(f"\n[bold]Services:[/bold] {', '.join(services)}")

        if show_content:
            console.print("\n[bold cyan]Compose Content:[/bold cyan]")
            console.print(yaml.dump(result.content, default_flow_style=False, sort_keys=False))

    except Exception as e:
        console.print(f"[red]✗ Resolution failed:[/red] {e}")
        if logger:
            logger.exception("Compose resolution failed")
        raise typer.Exit(1)


@app.command()
def version():
    """Show Tengil version."""
    console.print("Tengil v0.1.0 - The Overlord of Your Homelab")

if __name__ == "__main__":
    app()
