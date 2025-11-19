"""Discovery-focused CLI command group."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console

from tengil.cli_discover_helpers import (
    handle_compose_reverse,
    handle_docker_search,
    show_docker_compose_stacks,
    show_docker_containers,
    show_docker_images,
    show_docker_overview,
)
from tengil.cli_support import is_mock, print_success, print_warning
from tengil.discovery import ProxmoxDiscovery
from tengil.discovery.datasets import DatasetDiscovery

DiscoverApp = typer.Typer(
    help="Inspect Proxmox, Docker, and dataset state",
    add_completion=False,
)

_console: Console = Console()


def register_discover_commands(app: typer.Typer, console: Console) -> None:
    """Attach the discover command group to the root CLI."""
    global _console
    _console = console
    app.add_typer(DiscoverApp, name="discover")


@DiscoverApp.callback(invoke_without_command=True)
def discover_callback(
    ctx: typer.Context,
    host: Optional[str] = typer.Option(None, "--host", "-h", help="Proxmox host (IP or hostname)"),
    user: str = typer.Option("root", "--user", "-u", help="SSH user"),
    templates_flag: bool = typer.Option(False, "--templates", "-t", help="Show available LXC templates"),
    containers: bool = typer.Option(False, "--containers", "-c", help="Show existing LXC containers"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search for LXC templates"),
    docker_containers: bool = typer.Option(False, "--docker-containers", help="Show Docker containers"),
    docker_images: bool = typer.Option(False, "--docker-images", help="Show Docker images"),
    docker_compose: bool = typer.Option(False, "--docker-compose", help="Show Docker Compose stacks"),
    docker_search: Optional[str] = typer.Option(None, "--docker-search", help="Search Docker containers/images"),
    compose_reverse: Optional[str] = typer.Option(None, "--compose-reverse", help="Reverse-engineer compose from container"),
    docker_host: Optional[str] = typer.Option(None, "--docker-host", help="Docker host URL (tcp://host:2375, ssh://user@host)"),
    docker_context: Optional[str] = typer.Option(None, "--docker-context", help="Docker context to use"),
    all_containers: bool = typer.Option(False, "--all", "-a", help="Include stopped containers (Docker only)"),
) -> None:
    """Default `tg discover` behavior (Proxmox + Docker awareness)."""
    if ctx.invoked_subcommand:
        # Subcommands (e.g., datasets) will handle their own logic
        return

    from tengil.discovery.docker_discovery import DockerDiscovery

    docker_mode = any([
        docker_containers,
        docker_images,
        docker_compose,
        docker_search is not None,
        compose_reverse is not None,
    ])

    if docker_mode:
        try:
            discovery = DockerDiscovery(host=docker_host, context=docker_context)
        except Exception as err:  # pragma: no cover - defensive
            _console.print(f"[red]Error connecting to Docker: {err}[/red]")
            _console.print("[yellow]Make sure Docker is running and accessible[/yellow]")
            raise typer.Exit(1) from err

        if compose_reverse:
            handle_compose_reverse(discovery, compose_reverse, _console)
            return

        if docker_search:
            handle_docker_search(discovery, docker_search, _console)
            return

        if docker_containers:
            show_docker_containers(discovery, all_containers, _console)
            return

        if docker_images:
            show_docker_images(discovery, _console)
            return

        if docker_compose:
            show_docker_compose_stacks(discovery, _console)
            return

        show_docker_overview(discovery, _console)
        return

    discovery = ProxmoxDiscovery(host=host, user=user)

    if search:
        results = discovery.search_template(search)
        if results:
            _console.print(f"\n[cyan]Templates matching '{search}':[/cyan]")
            for template in results:
                template_type = template.get("type", "unknown")
                _console.print(f"  [{template_type}] [bold]{template['name']}[/bold]")
        else:
            _console.print(f"[yellow]No templates found matching '{search}'[/yellow]")
        return

    if containers:
        existing = discovery.get_existing_containers()
        if existing:
            _console.print("\n[cyan]Existing LXC Containers:[/cyan]")
            _console.print(f"{'VMID':<8} {'Status':<10} {'Name'}")
            _console.print("-" * 50)
            for entry in existing:
                status_color = "green" if entry["status"] == "running" else "yellow"
                _console.print(f"{entry['vmid']:<8} [{status_color}]{entry['status']:<10}[/{status_color}] {entry['name']}")
        else:
            _console.print("[yellow]No containers found[/yellow]")
        return

    if templates_flag:
        templates = discovery.get_available_templates()
        if not templates:
            _console.print("[yellow]No templates found. Run 'pveam update' on Proxmox to refresh.[/yellow]")
            return

        _console.print("\n[cyan]Available LXC Templates:[/cyan]")
        _console.print(f"[dim]Found {len(templates)} templates from Proxmox repository[/dim]\n")

        grouped: dict[str, list[dict]] = {}
        for template in templates:
            grouped.setdefault(template["type"], []).append(template)

        for template_type in sorted(grouped.keys()):
            entries = grouped[template_type]
            _console.print(f"[bold cyan]{template_type.upper()}:[/bold cyan] {len(entries)} templates")
            for entry in entries[:5]:
                name = entry["name"]
                simple_name = name.split("_")[0] if "_" in name else name
                _console.print(f"  {simple_name}")
            if len(entries) > 5:
                _console.print(f"  [dim]... and {len(entries) - 5} more[/dim]")
            _console.print()

        _console.print("[dim]Use --search <name> to find specific templates[/dim]")
        downloaded = discovery.get_downloaded_templates()
        if downloaded:
            _console.print(f"\n[green]Downloaded templates:[/green] {len(downloaded)}")
            for entry in downloaded:
                _console.print(f"  ✓ {entry['name']} ({entry['size']})")
        return

    _console.print("\n[cyan bold]Proxmox Discovery[/cyan bold]")
    if host:
        _console.print(f"[dim]Host: {host}[/dim]\n")

    existing = discovery.get_existing_containers()
    _console.print(f"[cyan]Existing Containers:[/cyan] {len(existing)}")
    if existing:
        for entry in existing[:5]:
            status_color = "green" if entry["status"] == "running" else "yellow"
            _console.print(f"  {entry['vmid']} - [{status_color}]{entry['status']}[/{status_color}] {entry['name']}")
        if len(existing) > 5:
            _console.print(f"  [dim]... and {len(existing) - 5} more[/dim]")

    templates = discovery.get_available_templates()
    _console.print(f"\n[cyan]Available Templates:[/cyan] {len(templates)}")
    if templates:
        for entry in templates[:5]:
            _console.print(f"  {entry['name']} ({entry['size']})")
        if len(templates) > 5:
            _console.print(f"  [dim]... and {len(templates) - 5} more[/dim]")

    _console.print("\n[dim]Run with --containers, --templates, or --search for more details[/dim]")


@DiscoverApp.command("datasets")
def discover_datasets(
    pool: str = typer.Option(..., "--pool", "-p", help="ZFS pool to analyze"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write discovery results to a file"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of YAML"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Only show summary counts"),
) -> None:
    """Discover existing datasets + NAS shares for a pool."""
    discovery = DatasetDiscovery(mock=is_mock())
    datasets = discovery.discover_pool(pool)

    if not datasets:
        print_warning(_console, f"No datasets discovered under pool '{pool}'")
        return

    result = {"pool": pool, "datasets": datasets}
    dataset_count = len(datasets)
    print_success(_console, f"Found {dataset_count} dataset(s) under {pool}")

    if quiet:
        return

    if json_output:
        import json
        rendered = json.dumps(result, indent=2)
    else:
        rendered = yaml.safe_dump(result, sort_keys=False)

    if output:
        output.write_text(rendered)
        print_success(_console, f"Wrote discovery results to {output}", prefix="💾")
    else:
        _console.print(rendered)
