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
        console.print(f"  1. Pull image:  [cyan]tg oci pull {app.image.split('/')[-1]}[/cyan]")
        if has_spec:
            console.print(f"  2. Deploy:      [cyan]tg apply packages/{app.name}-oci.yml[/cyan]")
        else:
            console.print(f"  2. Create spec or use 'tg oci install {app.name}' for snippet")
        
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

    @OciTyper.command("pull")
    def pull_command(
        image: str = typer.Argument(..., help="Image reference (e.g., alpine:latest, jellyfin/jellyfin:latest)"),
        registry: str = typer.Option(None, "--registry", "-r", help="Registry URL (default: docker.io)"),
    ):
        """Pull an OCI image to local cache using skopeo."""
        # Parse image reference
        if ':' in image:
            image_name, tag = image.rsplit(':', 1)
        else:
            image_name, tag = image, 'latest'
        
        console.print(f"[cyan]Pulling {image_name}:{tag}...[/cyan]")
        
        backend = OCIBackend()
        template_ref = backend.pull_image(image_name, tag, registry)
        
        if template_ref:
            console.print(f"[green]✓ Image pulled successfully[/green]")
            console.print(f"[dim]Template reference: {template_ref}[/dim]")
            console.print(f"\n[bold]Next steps:[/bold]")
            console.print(f"  1. Use in package spec: template: {template_ref}")
            console.print(f"  2. Or create container: pct create <vmid> {template_ref}")
        else:
            console.print(f"[red]✗ Failed to pull image[/red]")
            raise typer.Exit(1)

    @OciTyper.command("list")
    def list_command(
        format: str = typer.Option("table", "--format", "-f", help="Output format: table|json"),
    ):
        """List cached OCI templates."""
        template_dir = Path('/var/lib/vz/template/cache')
        
        if not template_dir.exists():
            console.print(f"[yellow]Template directory not found: {template_dir}[/yellow]")
            return
        
        # Find all .tar files (OCI archives)
        templates = sorted(template_dir.glob('*.tar'), key=lambda p: p.stat().st_mtime, reverse=True)
        
        if not templates:
            console.print("[yellow]No OCI templates found in cache[/yellow]")
            console.print(f"[dim]Use 'tg oci pull <image>' to download images[/dim]")
            return
        
        if format == "json":
            import json
            data = [
                {
                    "name": t.name,
                    "size": t.stat().st_size,
                    "modified": t.stat().st_mtime,
                    "path": str(t)
                }
                for t in templates
            ]
            console.print(json.dumps(data, indent=2))
            return
        
        # Table format
        table = Table(title="Cached OCI Templates")
        table.add_column("Template", style="cyan")
        table.add_column("Size", justify="right")
        table.add_column("Modified")
        
        for t in templates:
            size_mb = t.stat().st_size / (1024 * 1024)
            import datetime
            mtime = datetime.datetime.fromtimestamp(t.stat().st_mtime)
            table.add_row(
                t.name,
                f"{size_mb:.1f} MB",
                mtime.strftime("%Y-%m-%d %H:%M")
            )
        
        console.print(table)
        console.print(f"\n[dim]Location: {template_dir}[/dim]")

    @OciTyper.command("login")
    def login_command(
        registry: str = typer.Argument(..., help="Registry URL (e.g., docker.io, ghcr.io)"),
        username: str = typer.Option(None, "--username", "-u", help="Username"),
    ):
        """Authenticate with an OCI registry."""
        import subprocess
        
        console.print(f"[cyan]Logging in to {registry}...[/cyan]")
        
        cmd = ['skopeo', 'login', registry]
        if username:
            cmd.extend(['--username', username])
        
        try:
            subprocess.run(cmd, check=True)
            console.print(f"[green]✓ Successfully logged in to {registry}[/green]")
            console.print(f"[dim]Credentials stored in ~/.config/containers/auth.json[/dim]")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Login failed[/red]")
            raise typer.Exit(1)

    @OciTyper.command("logout")
    def logout_command(
        registry: str = typer.Argument(..., help="Registry URL"),
    ):
        """Remove authentication for an OCI registry."""
        import subprocess
        
        try:
            subprocess.run(['skopeo', 'logout', registry], check=True)
            console.print(f"[green]✓ Successfully logged out from {registry}[/green]")
        except subprocess.CalledProcessError:
            console.print(f"[red]✗ Logout failed[/red]")
            raise typer.Exit(1)

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
