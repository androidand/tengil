"""OCI/LXC app discovery and config scaffolding commands."""
from __future__ import annotations

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

from tengil.services.oci_capability import detect_oci_support
from tengil.services.oci_registry import OciRegistryCatalog, OciApp
from tengil.services.proxmox.backends.oci import OCIBackend

OciTyper = typer.Typer(help="OCI/LXC app helpers")


def register_oci_commands(root: typer.Typer, console: Console) -> None:
    """Attach OCI commands to the main CLI."""

    @OciTyper.command("catalog")
    def catalog_command(
        category: str = typer.Option(None, "--category", "-c", help="Filter by category (media, photos, files, etc.)"),
        search: str = typer.Option(None, "--search", "-s", help="Filter apps by name/image"),
        format: str = typer.Option("table", "--format", "-f", help="Output format: table|json"),
        list_categories: bool = typer.Option(False, "--list-categories", help="Show available categories"),
    ):
        """Browse the OCI app catalog with 31+ popular self-hosted applications."""
        # Show categories if requested
        if list_categories:
            categories = OciRegistryCatalog.get_categories()
            console.print("[bold cyan]Available Categories:[/bold cyan]")
            for cat in categories:
                apps_in_cat = OciRegistryCatalog.filter_by_category(cat)
                console.print(f"  [yellow]{cat}[/yellow] ({len(apps_in_cat)} apps)")
            return
        
        # Filter apps
        if category:
            apps = OciRegistryCatalog.filter_by_category(category)
            if not apps:
                console.print(f"[yellow]No apps found in category '{category}'[/yellow]")
                console.print(f"[dim]Use --list-categories to see available categories[/dim]")
                return
        elif search:
            apps = OciRegistryCatalog.search_apps(search)
            if not apps:
                console.print(f"[yellow]No apps matching '{search}'[/yellow]")
                return
        else:
            apps = OciRegistryCatalog.list_popular_apps()

        if format == "json":
            import json
            registries = OciRegistryCatalog.list_registries()
            payload = {
                "registries": [registry.__dict__ for registry in registries],
                "apps": [app.__dict__ for app in apps],
            }
            console.print(json.dumps(payload, indent=2))
            return

        # Table format - show apps grouped by category
        if category:
            header = f"Apps in category: {category}"
        elif search:
            header = f"Apps matching '{search}'"
        else:
            header = "OCI App Catalog"
        
        console.print(f"[bold cyan]{header}[/bold cyan] ({len(apps)} apps)\n")
        
        # Group by category for better readability
        from collections import defaultdict
        by_category = defaultdict(list)
        for app in apps:
            by_category[app.category].append(app)
        
        for cat in sorted(by_category.keys()):
            console.print(f"[bold yellow]{cat.upper()}[/bold yellow]")
            for app in by_category[cat]:
                console.print(f"  [cyan]{app.name:20}[/cyan] {app.description}")
            console.print()
        
        console.print(f"[dim]Total: {len(apps)} apps across {len(by_category)} categories[/dim]")
        console.print(f"[dim]Use 'tg oci info <app>' for details or 'tg oci search <term>' to search[/dim]")

    @OciTyper.command("status")
    def status_command(mock: bool = typer.Option(False, "--mock", help="Mock capability detection")):
        """Show whether the host appears OCI-capable (Proxmox 9.1+)."""
        cap = detect_oci_support(mock=mock)
        verdict = "[green]supported[/green]" if cap.supported else "[red]not detected[/red]"
        version = f" (pve {cap.pve_version})" if cap.pve_version else ""
        console.print(f"[bold cyan]OCI Capability:[/bold cyan] {verdict}{version} - {cap.reason}")
        if cap.hint:
            console.print(f"[dim]{cap.hint}[/dim]")

    @OciTyper.command("search")
    def search_command(
        query: str = typer.Argument(..., help="Search term (name or image substring)")
    ):
        """Search the OCI app catalog by name, image, or description."""
        results = OciRegistryCatalog.search_apps(query)
        if not results:
            console.print(f"[yellow]No apps matching '{query}'[/yellow]")
            console.print(f"[dim]Try 'tg oci catalog' to browse all apps[/dim]")
            return

        console.print(f"[bold cyan]Apps matching '{query}':[/bold cyan] ({len(results)} found)\n")
        
        # Group by category
        from collections import defaultdict
        by_category = defaultdict(list)
        for app in results:
            by_category[app.category].append(app)
        
        for cat in sorted(by_category.keys()):
            console.print(f"[bold yellow]{cat.upper()}[/bold yellow]")
            for app in by_category[cat]:
                console.print(f"  [cyan]{app.name:20}[/cyan] {app.description}")
            console.print()
        
        console.print(f"[dim]Use 'tg oci info <app>' for detailed information[/dim]")

    @OciTyper.command("info")
    def info_command(
        app_name: str = typer.Argument(..., help="App name (e.g., jellyfin, nextcloud)")
    ):
        """Show detailed information about a specific app from the catalog."""
        app = OciRegistryCatalog.get_app_by_name(app_name)
        if not app:
            console.print(f"[red]App '{app_name}' not found in catalog[/red]")
            console.print(f"[dim]Use 'tg oci search {app_name}' to find similar apps[/dim]")
            raise typer.Exit(1)
        
        # Show detailed app information
        console.print(f"\n[bold cyan]{app.name.upper()}[/bold cyan]")
        console.print(f"[dim]{app.description}[/dim]\n")
        
        console.print(f"[bold]Image:[/bold]       {app.image}")
        console.print(f"[bold]Registry:[/bold]    {app.registry}")
        console.print(f"[bold]Category:[/bold]    {app.category}")
        
        # Check if we have a package spec for this app
        from pathlib import Path
        package_path = Path(f"packages/{app.name}-oci.yml")
        has_spec = package_path.exists()
        
        if has_spec:
            console.print(f"\n[green]✓[/green] Package spec available: [cyan]packages/{app.name}-oci.yml[/cyan]")
            console.print(f"[dim]Deploy with: tg apply packages/{app.name}-oci.yml[/dim]")
        else:
            console.print(f"\n[yellow]⚠[/yellow] No package spec yet (contribute one!)")
        
        # Show pull command
        console.print(f"\n[bold]Quick Start:[/bold]")
        console.print(f"  • Create a spec: use 'tg oci install {app.name}' to generate a snippet")
        if has_spec:
            console.print(f"  • Deploy existing: [cyan]tg apply packages/{app.name}-oci.yml[/cyan]")
        
        # Show related apps in same category
        related = [a for a in OciRegistryCatalog.filter_by_category(app.category) if a.name != app.name]
        if related:
            console.print(f"\n[bold]Related apps in {app.category}:[/bold]")
            for rel in related[:3]:  # Show max 3
                console.print(f"  • [cyan]{rel.name}[/cyan] - {rel.description}")
        
        console.print()

    @OciTyper.command("install")
    def install_command(
        app_name: str = typer.Argument(..., help="App name (from search)"),
        runtime: str = typer.Option("oci", "--runtime", "-r", help="Preferred runtime: oci|lxc|docker-host"),
        dataset: str = typer.Option("appdata", "--dataset", "-d", help="Dataset name for app data"),
        mount: str = typer.Option("/data", "--mount", "-m", help="Mount path inside container"),
    ):
        """Render a tengil.yml snippet for the requested app."""
        app = _find_app(app_name)
        if not app:
            console.print(f"[red]App '{app_name}' not found in catalog[/red]")
            console.print("Run 'tg oci search <term>' to discover available apps.")
            raise typer.Exit(1)

        snippet = _render_snippet(app, runtime=runtime, dataset=dataset, mount=mount)
        console.print("[bold cyan]Add this to tengil.yml[/bold cyan]:\n")
        console.print(snippet)
        console.print("\n[dim]Tip: adjust dataset/pool to match your ZFS layout.[/dim]")

    root.add_typer(OciTyper, name="oci")


def _find_app(name: str) -> OciApp | None:
    q = name.lower()
    for app in OciRegistryCatalog.list_popular_apps():
        if app.name.lower() == q or q in app.image.lower():
            return app
    return None


def _format_app_line(app: OciApp) -> str:
    return f"- [green]{app.name:<14}[/green] {app.image}  [dim]{app.description}[/dim]"


def _render_snippet(app: OciApp, runtime: str, dataset: str, mount: str) -> str:
    """Return a YAML snippet that favors OCI/LXC with ZFS-backed storage."""
    runtime_note = "oci (preferred)" if runtime == "oci" else runtime
    return f"""apps:
  - name: {app.name}
    runtime: {runtime_note}
    image: {app.image}
    dataset: {dataset}
    mount: {mount}
    env: {{}}
    ports: []
    volumes: []
"""
