"""OCI/LXC app discovery and config scaffolding commands."""
from __future__ import annotations

import typer
from rich.console import Console

from tengil.services.oci_capability import detect_oci_support
from tengil.services.oci_registry import OciRegistryCatalog, OciApp

OciTyper = typer.Typer(help="OCI/LXC app helpers")


def register_oci_commands(root: typer.Typer, console: Console) -> None:
    """Attach OCI commands to the main CLI."""

    @OciTyper.command("catalog")
    def catalog_command(
        search: str = typer.Option(None, "--search", "-s", help="Filter apps by name/image"),
        format: str = typer.Option("table", "--format", "-f", help="Output format: table|json"),
        status: bool = typer.Option(False, "--status", help="Show host OCI capability"),
        mock: bool = typer.Option(False, "--mock", help="Mock capability detection"),
    ):
        """List registries and popular apps; optionally report OCI capability."""
        cap = detect_oci_support(mock=mock) if status else None
        registries = OciRegistryCatalog.list_registries()
        apps = OciRegistryCatalog.search_apps(search) if search else OciRegistryCatalog.list_popular_apps()

        if format == "json":
            import json
            payload = {
                "registries": [registry.__dict__ for registry in registries],
                "apps": [app.__dict__ for app in apps],
                "capability": cap.__dict__ if cap else None,
            }
            console.print(json.dumps(payload, indent=2))
            return

        if cap:
            verdict = "[green]supported[/green]" if cap.supported else "[red]not detected[/red]"
            version = f" (pve {cap.pve_version})" if cap.pve_version else ""
            console.print(f"[bold cyan]OCI Capability:[/bold cyan] {verdict}{version} - {cap.reason}")
            if cap.hint:
                console.print(f"[dim]{cap.hint}[/dim]")
            console.print()

        console.print("[bold cyan]OCI Registries[/bold cyan]")
        for reg in registries:
            note = f" ({reg.note})" if reg.note else ""
            console.print(f"- [yellow]{reg.name}[/yellow]: {reg.url}{note}")

        console.print("\n[bold cyan]Popular OCI Apps[/bold cyan]")
        for app in apps:
            console.print(_format_app_line(app))

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
        """Search known OCI apps (static curated list for now)."""
        results = OciRegistryCatalog.search_apps(query)
        if not results:
            console.print("[yellow]No matching apps found[/yellow]")
            return

        console.print(f"[bold cyan]Apps matching '{query}':[/bold cyan]")
        for app in results:
            console.print(_format_app_line(app))

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
