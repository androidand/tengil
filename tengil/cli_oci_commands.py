"""OCI/LXC app discovery and config scaffolding commands."""
from __future__ import annotations

import typer
from pathlib import Path
from typing import List, Set
from rich.console import Console
from rich.table import Table

from tengil.cli_support import is_mock
from tengil.services.oci_capability import detect_oci_support
from tengil.services.oci_registry import OciRegistryCatalog, OciApp
from tengil.services.proxmox.backends.oci import OCIBackend
from tengil.services.proxmox.containers.discovery import ContainerDiscovery

OciTyper = typer.Typer(help="OCI/LXC app helpers")


def register_oci_commands(root: typer.Typer, console: Console) -> None:
    """Attach OCI commands to the main CLI."""

    @OciTyper.command("catalog")
    def catalog_command(
        category: str = typer.Option(None, "--category", "-c", help="Filter by category (media, photos, files, etc.)"),
        format: str = typer.Option("table", "--format", "-f", help="Output format: table|json"),
        all_apps: bool = typer.Option(False, "--all", help="Show all apps (default shows popular subset)"),
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
        
        # Get apps to display
        if category:
            apps = OciRegistryCatalog.filter_by_category(category)
            if not apps:
                console.print(f"[yellow]No apps found in category '{category}'[/yellow]")
                console.print(f"[dim]Use --list-categories to see available categories[/dim]")
                return
        else:
            all_catalog_apps = OciRegistryCatalog.list_popular_apps()
            if all_apps:
                apps = all_catalog_apps
            else:
                # Show popular subset (first 2-3 from each category)
                from collections import defaultdict
                by_category = defaultdict(list)
                for app in all_catalog_apps:
                    by_category[app.category].append(app)
                
                popular_apps = []
                for cat_apps in by_category.values():
                    popular_apps.extend(cat_apps[:2])  # First 2 from each category
                apps = popular_apps

        if format == "json":
            import json
            registries = OciRegistryCatalog.list_registries()
            payload = {
                "registries": [registry.__dict__ for registry in registries],
                "apps": [app.__dict__ for app in apps],
                "total_apps": len(apps),
                "total_categories": len(set(app.category for app in apps))
            }
            console.print(json.dumps(payload, indent=2))
            return

        # Table format with proper Rich table
        if category:
            title = f"Apps in category: {category}"
        elif all_apps:
            title = "Complete OCI App Catalog"
        else:
            title = "Popular OCI Apps"
        
        table = Table(title=f"{title} ({len(apps)} apps)", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="cyan", width=15)
        table.add_column("Description", style="white")
        table.add_column("Category", style="yellow", width=12)
        table.add_column("Registry", style="dim", width=10)
        
        # Sort apps by category, then name
        sorted_apps = sorted(apps, key=lambda x: (x.category, x.name))
        
        for app in sorted_apps:
            # Check if package spec exists
            from pathlib import Path
            package_path = Path(f"packages/{app.name}-oci.yml")
            name_display = f"{app.name} ✓" if package_path.exists() else app.name
            
            table.add_row(
                name_display,
                app.description,
                app.category,
                app.registry
            )
        
        console.print(table)
        
        if not all_apps and not category:
            console.print(f"\n[dim]Showing popular apps. Use --all to see all {OciRegistryCatalog.count_apps()} apps.[/dim]")
        
        console.print(f"[dim]Use 'tg oci info <app>' for details • 'tg oci search <term>' to search • ✓ = package spec available[/dim]")

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

    @OciTyper.command("remove")
    def remove_command(
        image: str = typer.Argument(..., help="Image/tag or template filename to remove (e.g., 'alpine:latest' or 'alpine-*.tar')"),
        force: bool = typer.Option(False, "--force", "-f", help="Force removal without confirmation"),
    ):
        """Delete cached OCI templates (supports wildcards and safety checks)."""
        backend = OCIBackend(mock=is_mock())
        discovery = ContainerDiscovery(mock=is_mock())

        if not backend.template_dir.exists():
            console.print(f"[yellow]Template directory not found: {backend.template_dir}[/yellow]")
            raise typer.Exit(1)

        matches = _resolve_template_matches(backend.template_dir, image)
        if not matches:
            console.print(f"[yellow]No cached templates match '{image}'[/yellow]")
            raise typer.Exit(1)

        in_use_templates = _templates_in_use(discovery)
        still_in_use = [m for m in matches if m.name in in_use_templates]
        if still_in_use:
            console.print("[red]Cannot remove template(s) currently used by containers:[/red]")
            for tmpl in still_in_use:
                console.print(f"  - {tmpl.name}")
            raise typer.Exit(1)

        total_size = sum(m.stat().st_size for m in matches)
        total_mb = total_size / (1024 * 1024)

        console.print(f"[cyan]Found {len(matches)} template(s) totalling {total_mb:.1f} MB:[/cyan]")
        for tmpl in matches:
            size_mb = tmpl.stat().st_size / (1024 * 1024)
            console.print(f"  - {tmpl.name} ({size_mb:.1f} MB)")

        if not force:
            confirm = typer.confirm(f"Remove {len(matches)} template(s)?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                raise typer.Exit(0)

        removed = 0
        for tmpl in matches:
            try:
                tmpl.unlink()
                removed += 1
            except Exception as e:
                console.print(f"[red]Error removing {tmpl.name}: {e}[/red]")

        if removed == len(matches):
            console.print(f"[green]✓[/green] Removed {removed} template(s)")
        else:
            console.print(f"[yellow]Removed {removed}/{len(matches)} template(s)[/yellow]")
            raise typer.Exit(1)

    @OciTyper.command("prune")
    def prune_command(
        dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed without deleting"),
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    ):
        """Remove all unused OCI templates to free up storage space."""
        backend = OCIBackend(mock=is_mock())
        discovery = ContainerDiscovery(mock=is_mock())

        if not backend.template_dir.exists():
            console.print(f"[yellow]Template directory not found: {backend.template_dir}[/yellow]")
            raise typer.Exit(1)

        templates = sorted(backend.template_dir.glob("*.tar"))
        if not templates:
            console.print("[yellow]No cached templates found[/yellow]")
            return

        in_use_templates = _templates_in_use(discovery)
        unused_templates = [tmpl for tmpl in templates if tmpl.name not in in_use_templates]

        if not unused_templates:
            console.print("[yellow]All cached templates are referenced by containers; nothing to prune[/yellow]")
            return

        total_size = sum(tmpl.stat().st_size for tmpl in unused_templates)
        total_mb = total_size / (1024 * 1024)

        console.print(f"[cyan]Pruning {len(unused_templates)} unused template(s) ({total_mb:.1f} MB):[/cyan]")
        for tmpl in unused_templates:
            size_mb = tmpl.stat().st_size / (1024 * 1024)
            console.print(f"  - {tmpl.name} ({size_mb:.1f} MB)")

        if dry_run:
            console.print("\n[dim]Dry run - nothing removed[/dim]")
            return

        if not force:
            confirm = typer.confirm(f"Remove {len(unused_templates)} template(s)?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                raise typer.Exit(0)

        removed = 0
        for tmpl in unused_templates:
            try:
                tmpl.unlink()
                removed += 1
            except Exception as e:
                console.print(f"[red]Error removing {tmpl.name}: {e}[/red]")

        console.print(f"[green]✓[/green] Removed {removed}/{len(unused_templates)} template(s)")

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


def _templates_in_use(discovery: ContainerDiscovery) -> Set[str]:
    """Return template filenames referenced by existing containers."""
    in_use: Set[str] = set()
    try:
        containers = discovery.get_all_containers_info()
    except Exception:
        containers = []

    for container in containers or []:
        template_ref = container.get("template")
        if not template_ref:
            continue
        # Handle values like local:vztmpl/alpine-latest.tar
        name = template_ref.split("/")[-1]
        if "vztmpl/" in template_ref:
            name = template_ref.split("vztmpl/")[-1]
        in_use.add(name)
    return in_use


def _resolve_template_matches(template_dir: Path, target: str) -> List[Path]:
    """Translate image/tag input to template filename pattern and return matches."""
    if target.endswith(".tar"):
        pattern = target
    else:
        last_colon = target.rfind(":")
        last_slash = target.rfind("/")
        if last_colon > last_slash:
            image_part = target[:last_colon]
            tag = target[last_colon + 1 :] or "latest"
        else:
            image_part = target
            tag = "latest"

        base_name = image_part.split("/")[-1]
        pattern = f"{base_name}-{tag}.tar"

    # Use glob to support wildcards
    matches = sorted(template_dir.glob(pattern))
    return matches
