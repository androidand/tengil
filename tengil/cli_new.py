"""Tengil CLI - Simplified to 8 essential commands only.

No abstraction layers, no command modules, no complexity.
Just the core functionality users actually need.
"""
import os
import typer
from pathlib import Path
from rich.console import Console
from typing import Optional

from tengil.core_new import Tengil

app = typer.Typer(
    name="tengil",
    help="Declarative infrastructure for Proxmox homelabs",
    add_completion=False
)

console = Console()


def is_mock() -> bool:
    """Check if running in mock mode."""
    return os.environ.get('TG_MOCK') == '1'


@app.command()
def diff(
    config: str = typer.Option("tengil.yml", "--config", "-c", help="Config file path")
):
    """Show what changes would be made (like 'terraform plan')."""
    try:
        tengil = Tengil(config, mock=is_mock())
        changes = tengil.diff()
        console.print(changes.format())
        
        if len(changes) > 0:
            console.print(f"\n[yellow]Run 'tg apply' to make these changes[/yellow]")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def apply(
    config: str = typer.Option("tengil.yml", "--config", "-c", help="Config file path"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Apply the configuration (like 'terraform apply')."""
    try:
        tengil = Tengil(config, mock=is_mock())
        changes = tengil.diff()
        
        if len(changes) == 0:
            console.print("[green]✓[/green] Infrastructure is up to date")
            return
        
        # Show plan
        console.print(changes.format())
        
        # Confirm unless --yes or mock
        if not yes and not is_mock():
            if not typer.confirm(f"\nApply {len(changes)} changes?"):
                console.print("[yellow]Cancelled[/yellow]")
                return
        
        # Apply changes
        console.print(f"\n[cyan]Applying {len(changes)} changes...[/cyan]")
        results = tengil.apply(changes)
        
        if results["failed"] > 0:
            console.print(f"[red]✗[/red] {results['failed']} changes failed")
            raise typer.Exit(1)
        else:
            console.print(f"[green]✓[/green] Applied {results['success']} changes successfully")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def init(
    package: Optional[str] = typer.Option(None, "--package", "-p", help="Package name"),
    pool: str = typer.Option("tank", "--pool", help="ZFS pool name")
):
    """Initialize a new tengil.yml configuration."""
    config_path = Path("tengil.yml")

    if config_path.exists():
        if not typer.confirm("tengil.yml exists. Overwrite?"):
            return

    if package:
        # Load from package
        try:
            from tengil.core_new import Config
            config = Config.from_package(package, pool)
            import yaml
            config_path.write_text(yaml.dump(config.data, default_flow_style=False, sort_keys=False))
            console.print(f"[green]✓[/green] Created {config_path} from package '{package}'")
            console.print("\n[cyan]Next steps:[/cyan]")
            console.print("  1. Review tengil.yml")
            console.print("  2. Run 'tg diff' to preview changes")
            console.print("  3. Run 'tg apply' to create infrastructure")
            return
        except FileNotFoundError:
            console.print(f"[red]Error:[/red] Package '{package}' not found")
            console.print("\nRun 'tg packages' to see available packages")
            raise typer.Exit(1)

    # Create basic config
    basic_config = f"""pools:
  {pool}:
    datasets:
      media:
        profile: media
        containers:
          - name: jellyfin
            template: debian-12-standard
            mount: /media
            memory: 4096
            cores: 2
        shares:
          smb:
            name: Media
            browseable: yes

      appdata:
        profile: appdata
        containers:
          - name: portainer
            template: debian-12-standard
            mount: /data
            memory: 2048
            cores: 1
            privileged: true
            post_install:
              - docker
              - portainer
"""

    config_path.write_text(basic_config)
    console.print(f"[green]✓[/green] Created {config_path}")
    console.print("\n[cyan]Next steps:[/cyan]")
    console.print("  1. Edit tengil.yml to customize")
    console.print("  2. Run 'tg diff' to preview changes")
    console.print("  3. Run 'tg apply' to create infrastructure")


@app.command()
def packages():
    """List available packages."""
    from tengil.core_new import Config

    pkg_list = Config.list_packages()

    if not pkg_list:
        console.print("[yellow]No packages found[/yellow]")
        return

    console.print(f"[bold cyan]Available Packages ({len(pkg_list)}):[/bold cyan]\n")

    # Group by category
    by_category = {}
    for pkg in pkg_list:
        cat = pkg["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(pkg)

    for category, pkgs in sorted(by_category.items()):
        console.print(f"[bold]{category.upper()}[/bold]")
        for pkg in pkgs:
            difficulty_color = {
                "beginner": "green",
                "intermediate": "yellow",
                "advanced": "red"
            }.get(pkg["difficulty"], "white")

            console.print(f"  [cyan]{pkg['name']:30}[/cyan] [{difficulty_color}]{pkg['difficulty']:12}[/{difficulty_color}] {pkg['description']}")
        console.print()

    console.print("[dim]Use 'tg init --package <name>' to create a config from a package[/dim]")


@app.command()
def discover():
    """Discover existing infrastructure."""
    console.print("[yellow]Discovery coming soon![/yellow]")
    console.print("\nFor now, manually create tengil.yml based on existing setup.")


@app.command()
def rollback():
    """Rollback to previous state."""
    console.print("[yellow]Rollback coming soon![/yellow]")
    console.print("\nFor now, manually revert changes using Proxmox GUI.")


@app.command()
def doctor():
    """Check system health and requirements."""
    console.print("[bold cyan]Tengil Doctor[/bold cyan]\n")
    
    # Check ZFS
    try:
        import subprocess
        result = subprocess.run(["zfs", "version"], capture_output=True, text=True)
        if result.returncode == 0:
            console.print("[green]✓[/green] ZFS available")
        else:
            console.print("[red]✗[/red] ZFS not found")
    except FileNotFoundError:
        console.print("[red]✗[/red] ZFS not installed")
    
    # Check Proxmox
    try:
        result = subprocess.run(["pct", "list"], capture_output=True, text=True)
        if result.returncode == 0:
            console.print("[green]✓[/green] Proxmox LXC available")
        else:
            console.print("[red]✗[/red] Proxmox LXC not available")
    except FileNotFoundError:
        console.print("[red]✗[/red] Proxmox not installed")
    
    # Check config
    if Path("tengil.yml").exists():
        console.print("[green]✓[/green] tengil.yml found")
    else:
        console.print("[yellow]⚠[/yellow] No tengil.yml (run 'tg init')")


@app.command()
def version():
    """Show Tengil version."""
    console.print("Tengil v2.0.0 - Simplified Architecture")
    console.print("The overlord of your homelab, now with 80% less bloat!")


if __name__ == "__main__":
    app()