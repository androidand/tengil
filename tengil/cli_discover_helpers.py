"""Helper functions for Docker discovery CLI output."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table


def show_docker_containers(discovery: Any, show_all: bool, console: Console) -> None:
    """Render Docker containers in a table."""
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
            ports_str += f" +{len(container.ports) - 2}"

        table.add_row(
            container.id[:12],
            container.name,
            container.image,
            f"[{status_style}]{container.status}[/{status_style}]",
            ports_str,
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(containers)} container(s)[/dim]")


def show_docker_images(discovery: Any, console: Console) -> None:
    """Render Docker images in a table."""
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
            image.created,
        )

    console.print(table)


def show_docker_compose_stacks(discovery: Any, console: Console) -> None:
    """Render Docker Compose stacks."""
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
        container_list = ", ".join(stack.containers[:3])
        if len(stack.containers) > 3:
            container_list += f" +{len(stack.containers) - 3}"

        table.add_row(stack.project, str(len(stack.services)), container_list)

    console.print(table)
    console.print(f"\n[dim]Found {len(stacks)} stack(s)[/dim]")


def handle_docker_search(discovery: Any, pattern: str, console: Console) -> None:
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


def handle_compose_reverse(discovery: Any, container_id: str, console: Console) -> None:
    """Reverse-engineer Docker Compose from a running container."""
    console.print(f"\n[cyan]Reverse-engineering compose for container: {container_id}[/cyan]\n")

    compose = discovery.reverse_engineer_compose(container_id)
    if not compose:
        console.print(f"[red]Container not found: {container_id}[/red]")
        return

    compose_yaml = yaml.dump(compose, default_flow_style=False, sort_keys=False)
    console.print("[bold]Generated Docker Compose:[/bold]")
    console.print(f"[dim]{'-' * 60}[/dim]")
    console.print(compose_yaml)
    console.print(f"[dim]{'-' * 60}[/dim]")

    if Confirm.ask("\nSave to compose_cache?", default=False):
        service_name = list(compose["services"].keys())[0]
        default_name = service_name.replace("_", "-").lower()

        app_name = Prompt.ask("App name for cache", default=default_name)

        cache_dir = Path.cwd() / "compose_cache" / app_name
        cache_dir.mkdir(parents=True, exist_ok=True)

        compose_file = cache_dir / "docker-compose.yml"
        compose_file.write_text(compose_yaml)

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


def show_docker_overview(discovery: Any, console: Console) -> None:
    """Render a summary of Docker containers, images, and stacks."""
    console.print("\n[cyan bold]Docker Discovery Overview[/cyan bold]\n")

    containers = discovery.list_containers(all=False)
    console.print(f"[cyan]Running Containers:[/cyan] {len(containers)}")
    for container in containers[:3]:
        console.print(f"  ● {container.name} ({container.image})")
    if len(containers) > 3:
        console.print(f"  [dim]... and {len(containers) - 3} more[/dim]")

    images = discovery.list_images()
    console.print(f"\n[cyan]Local Images:[/cyan] {len(images)}")
    for image in images[:3]:
        console.print(f"  • {image.repository}:{image.tag}")
    if len(images) > 3:
        console.print(f"  [dim]... and {len(images) - 3} more[/dim]")

    stacks = discovery.list_compose_stacks()
    if stacks:
        console.print(f"\n[cyan]Compose Stacks:[/cyan] {len(stacks)}")
        for stack in stacks[:3]:
            console.print(f"  📦 {stack.project} ({len(stack.services)} services)")
        if len(stacks) > 3:
            console.print(f"  [dim]... and {len(stacks) - 3} more[/dim]")

    console.print("\n[dim]Run with --docker-containers, --docker-images, or --docker-compose for details[/dim]")
