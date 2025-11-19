"""Package management CLI commands - install, templates, packages."""
import subprocess
from typing import Optional

import typer
from rich.console import Console

from tengil.cli_support import is_mock
from tengil.core.package_loader import PackageLoader
from tengil.discovery import ProxmoxDiscovery
from tengil.smart_suggestions import SmartContainerMatcher

# Module-level console instance (will be set by register function)
console: Console = Console()


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
    from tengil.cli_support import print_warning

    discovery = ProxmoxDiscovery(host=host, user=user)
    matcher = SmartContainerMatcher(discovery, console)

    if apps:
        # Generate and optionally run install script
        app_list = [a.strip() for a in apps.split(',')]
        script = matcher.generate_install_script(dataset_type, app_list)

        if script_only:
            console.print(script)
        else:
            print_warning(console, "Automatic installation not yet implemented")
            console.print("[dim]Use --script-only to generate script, then run manually on Proxmox[/dim]")
    else:
        # Show smart suggestions
        matcher.show_smart_suggestions(dataset_type)


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
                console.print("\n[bold]Components:[/bold]")
                for comp in pkg.components:
                    console.print(f"  • {comp}")

            if pkg.requirements:
                console.print("\n[bold]System Requirements:[/bold]")
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
                console.print("\n[bold]Customization Options:[/bold]")
                for prompt in pkg.prompts:
                    default_str = f" (default: {prompt.default})" if prompt.default else ""
                    console.print(f"  • {prompt.prompt}{default_str}")

            if pkg.related:
                console.print("\n[bold]Related Packages:[/bold]")
                for rel in pkg.related:
                    console.print(f"  • {rel}")

            if pkg.notes:
                console.print("\n[bold]Notes:[/bold]")
                console.print(pkg.notes)

            console.print(f"\n[dim]Install with: tg init --package {pkg.slug}[/dim]")

        except FileNotFoundError as err:
            console.print(f"[red]Error: Package not found: {query}[/red]")
            console.print("\n[dim]Use 'tg packages list' to see available packages[/dim]")
            raise typer.Exit(1) from err
        except Exception as err:
            console.print(f"[red]Error loading package: {err}[/red]")
            raise typer.Exit(1) from err

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


def register_package_commands(
    app: typer.Typer,
    shared_console: Console,
    shared_template_loader=None
):
    """Register package management commands with the main Typer app.

    Args:
        app: Main Typer application
        shared_console: Shared Rich console instance
        shared_template_loader: Not used here, for API consistency
    """
    global console
    console = shared_console

    # Register commands
    app.command()(install)
    app.command()(templates)
    app.command()(packages)
