#!/usr/bin/env python3
"""Tengil CLI - The overlord of your homelab."""
import typer
import os
import yaml
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
from tengil.services.proxmox import ProxmoxManager
from tengil.services.nas import NASManager
from tengil.core.state_store import StateStore
from tengil.core.importer import InfrastructureImporter
from tengil.core.template_loader import TemplateLoader
from tengil.core.snapshot_manager import SnapshotManager
from tengil.core.recovery import RecoveryManager
from tengil.recommendations import show_all_recommendations, show_dataset_recommendations
from tengil.discovery import ProxmoxDiscovery
from tengil.smart_suggestions import SmartContainerMatcher

app = typer.Typer(
    name="tengil",
    help="Tengil - Declarative ZFS and Proxmox orchestration",
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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
):
    """Show what changes would be made."""
    try:
        # Load configuration
        config_path = find_config(config)
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        # Flatten all pools into full dataset paths
        orchestrator = PoolOrchestrator(loader, ZFSManager())
        all_desired, all_current = orchestrator.flatten_pools()
        
        # Calculate diff across all pools
        engine = DiffEngine(all_desired, all_current)
        engine.calculate_diff()
        
        # Display plan
        if engine.changes:
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
    dry_run: bool = typer.Option(False, "--dry-run", help="Show actions without applying")
):
    """Apply the configuration."""
    try:
        # Load configuration
        config_path = find_config(config)
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        # Flatten all pools into full dataset paths
        orchestrator = PoolOrchestrator(loader, ZFSManager(mock=dry_run))
        all_desired, all_current = orchestrator.flatten_pools()
        
        # Calculate diff across all pools
        engine = DiffEngine(all_desired, all_current)
        changes = engine.calculate_diff()
        
        if not changes:
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
        
        # Initialize safety guard
        from tengil.core.safety import get_safety_guard
        safety = get_safety_guard(mock=dry_run)
        
        # Initialize state tracking
        state = StateStore()
        
        # Initialize managers (pass state to ZFS for mock mode persistence)
        zfs = ZFSManager(mock=dry_run, state_store=state)
        proxmox = ProxmoxManager(mock=dry_run)
        nas = NASManager(mock=dry_run)
        
        # Apply changes using ChangeApplicator
        applicator = ChangeApplicator(zfs, proxmox, nas, state, console)
        applicator.apply_changes(changes, all_desired)
        
        # Show state summary
        stats = state.get_stats()
        console.print("\n[cyan]State Summary:[/cyan]")
        console.print(f"  Datasets managed: {stats['datasets_managed']}")
        console.print(f"    Created by Tengil: {stats['datasets_created']}")
        console.print(f"    Pre-existing: {stats['datasets_external']}")
        console.print(f"  Container mounts: {stats['mounts_managed']}")
        console.print(f"  SMB shares: {stats['smb_shares']}")
        console.print(f"  NFS exports: {stats['nfs_shares']}")
        console.print(f"\n[dim]State saved to: {state.state_file}[/dim]")
        
        console.print("\n[green]✓[/green] Apply complete")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

@app.command()
def init(
    template: Optional[str] = typer.Option(None, "--template", "-t", 
                                          help="Template name (e.g., homelab, media-server)"),
    templates: Optional[str] = typer.Option(None, "--templates",
                                           help="Comma-separated templates to combine"),
    datasets: Optional[str] = typer.Option(None, "--datasets", 
                                          help="Comma-separated dataset names to include"),
    pool: str = typer.Option("tank", "--pool", "-p", help="ZFS pool name"),
    list_templates: bool = typer.Option(False, "--list-templates", help="List available templates"),
    list_datasets: bool = typer.Option(False, "--list-datasets", help="List available datasets")
):
    """Initialize a new Tengil configuration.
    
    Examples:
        tg init --template homelab                  # Use homelab template
        tg init --templates homelab,media-server    # Combine multiple templates
        tg init --datasets movies,tv,photos         # Select specific datasets
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
    config_path = Path("tengil.yml")
    if config_path.exists():
        console.print("[yellow]Warning:[/yellow] tengil.yml already exists")
        if not typer.confirm("Overwrite?"):
            return
    
    try:
        configs_to_merge = []
        
        # Load from --datasets flag
        if datasets:
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
        
        # Merge all configurations
        merged_config = template_loader.merge_configs(configs_to_merge)
        merged_config["pool"] = pool
        
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

@app.command()
def discover(
    host: Optional[str] = typer.Option(None, "--host", "-h", help="Proxmox host (IP or hostname)"),
    user: str = typer.Option("root", "--user", "-u", help="SSH user"),
    templates: bool = typer.Option(False, "--templates", "-t", help="Show available templates"),
    containers: bool = typer.Option(False, "--containers", "-c", help="Show existing containers"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search for template")
):
    """Discover available LXC templates and containers on Proxmox.
    
    Examples:
        tg discover --containers                    # List existing containers
        tg discover --templates                     # List available templates
        tg discover --search jellyfin               # Search for jellyfin template
        tg discover --host 192.168.1.42 --templates # Check remote Proxmox
    """
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
def version():
    """Show Tengil version."""
    console.print("Tengil v0.1.0 - The Overlord of Your Homelab")

if __name__ == "__main__":
    app()
