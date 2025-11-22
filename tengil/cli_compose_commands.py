"""Docker Compose command group."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from tengil.cli_support import print_error, print_success, print_warning
from tengil.core.package_loader import Package, PackageLoader
from tengil.services.compose_converter import ComposeConverter
from tengil.services.docker_compose import ComposeAnalyzer, ComposeResolver

ComposeApp = typer.Typer(help="Analyze and resolve Docker Compose files", add_completion=False)

_console: Console = Console()


def register_compose_commands(app: typer.Typer, console: Console) -> None:
    """Attach compose commands to the primary CLI."""
    global _console
    _console = console
    app.add_typer(ComposeApp, name="compose")


@ComposeApp.command("analyze")
def compose_analyze(
    source: str = typer.Argument(..., help="Path or URL to docker-compose.yml"),
) -> None:
    """Inspect a docker-compose.yml and summarize infrastructure needs."""
    analyzer = ComposeAnalyzer()
    try:
        requirements = analyzer.analyze(source)
    except Exception as exc:  # pragma: no cover - CLI guard
        print_error(_console, f"Failed to analyze {source}: {exc}")
        raise typer.Exit(1) from exc

    if requirements.volumes:
        table = Table(title="Host Volume Mounts", show_header=True)
        table.add_column("Service", style="cyan")
        table.add_column("Host Path", style="bold")
        table.add_column("Container Path", style="blue")
        table.add_column("Mode", style="dim")
        for mount in requirements.volumes:
            mode = "ro" if mount.readonly else "rw"
            table.add_row(mount.service, mount.host, mount.container, mode)
        _console.print(table)
    else:
        _console.print("[yellow]No host bind mounts detected[/yellow]")

    if requirements.secrets:
        secrets_list = ", ".join(sorted(requirements.secrets))
        _console.print(f"\n[cyan]Secrets requiring values:[/cyan] {secrets_list}")

    if requirements.ports:
        _console.print(f"[cyan]Ports exposed:[/cyan] {', '.join(requirements.ports)}")

    _console.print(f"[dim]Services analyzed:[/dim] {', '.join(requirements.services)}")
    print_success(_console, "Compose analysis complete")


@ComposeApp.command("validate")
def compose_validate(
    source: str = typer.Argument(..., help="Path or URL to docker-compose.yml"),
) -> None:
    """Validate that a compose file can be parsed and analyzed."""
    analyzer = ComposeAnalyzer()
    try:
        analyzer.analyze(source)
    except Exception as exc:
        print_error(_console, f"{source} is not a valid compose file: {exc}")
        raise typer.Exit(1) from exc

    print_success(_console, f"{source} looks good")


@ComposeApp.command("resolve")
def compose_resolve(
    package: str = typer.Argument(..., help="Package slug or path to package YAML"),
    show_compose: bool = typer.Option(False, "--show-compose", help="Print resolved compose to stdout"),
    save_to_cache: bool = typer.Option(False, "--save-cache", help="Write compose to compose_cache/<slug>/docker-compose.yml"),
) -> None:
    """Run the compose resolver for a package definition."""
    loader = PackageLoader()
    try:
        pkg = _load_package(loader, package)
    except Exception as exc:
        print_error(_console, str(exc))
        raise typer.Exit(1) from exc

    if not pkg.docker_compose:
        print_error(_console, f"Package '{pkg.slug}' does not define docker_compose sources")
        raise typer.Exit(2)

    compose_spec = _first_compose_source(pkg.docker_compose)
    resolver = ComposeResolver()

    try:
        result = resolver.resolve(compose_spec)
    except Exception as exc:  # pragma: no cover - relies on network/cache
        print_error(_console, f"Failed to resolve compose for {pkg.slug}: {exc}")
        raise typer.Exit(1) from exc

    print_success(
        _console,
        f"Resolved compose for {pkg.slug} via {result.source_type}",
    )
    _console.print(f"[dim]Source:[/dim] {result.source_path}")
    _console.print(f"[dim]Services:[/dim] {', '.join(result.content.get('services', {}).keys())}")

    rendered = yaml.safe_dump(result.content, sort_keys=False)

    if save_to_cache:
        cache_path = Path("compose_cache") / pkg.slug / "docker-compose.yml"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(rendered)
        print_success(_console, f"Saved compose to {cache_path}", prefix="💾")

    if show_compose:
        _console.print("\n[bold]Resolved Compose:[/bold]\n")
        _console.print(rendered)


def _load_package(loader: PackageLoader, identifier: str) -> Package:
    """Load a package by slug or explicit file path."""
    package_path = Path(identifier)
    if package_path.exists():
        return loader.load_package_file(package_path)

    return loader.load_package(identifier)


def _first_compose_source(compose_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Return the primary compose source entry."""
    sources = compose_spec.get("sources")
    if isinstance(sources, list) and sources:
        return sources[0]
    return compose_spec


@ComposeApp.command("convert")
def compose_convert(
    source: str = typer.Argument(..., help="Path or URL to docker-compose.yml"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save config to file (e.g., tengil.yml)"),
    pool: str = typer.Option("tank", "--pool", "-p", help="ZFS pool to use"),
    app_name: Optional[str] = typer.Option(None, "--app-name", "-a", help="Application name (auto-detected if not provided)"),
    show_preview: bool = typer.Option(True, "--preview/--no-preview", help="Show preview before saving"),
) -> None:
    """Convert a Docker Compose file into a Tengil configuration.

    This command analyzes a Docker Compose file and automatically generates
    a Tengil YAML config with:
    - ZFS datasets mapped from compose volumes with optimal profiles
    - Container specs with Docker Engine enabled
    - Resource allocations based on app type
    - Secret detection for environment variables

    Examples:
        tg compose convert docker-compose.yml --output tengil.yml
        tg compose convert https://github.com/immich-app/immich/docker-compose.yml
        tg compose convert ./compose.yml --app-name immich --pool storage
    """
    converter = ComposeConverter()

    try:
        result = converter.convert(source, pool=pool, app_name=app_name)
    except Exception as exc:
        print_error(_console, f"Failed to convert {source}: {exc}")
        raise typer.Exit(1) from exc

    # Show summary
    _console.print("[bold cyan]Conversion Summary[/bold cyan]")
    _console.print(f"  App: [bold]{result.app_name}[/bold]")
    _console.print(f"  Pool: {result.pool}")
    _console.print(f"  Datasets: {len(result.datasets)}")
    _console.print(f"  Resources: {result.container_memory}MB RAM, {result.container_cores} cores")
    _console.print(f"  Services: {', '.join(result.services)}")

    if result.secrets_needed:
        _console.print(f"  Secrets: [yellow]{', '.join(result.secrets_needed)}[/yellow]")

    if result.ports:
        _console.print(f"  Ports: {', '.join(result.ports)}")

    # Show warnings
    if result.warnings:
        _console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for warning in result.warnings:
            print_warning(_console, warning)

    # Show dataset details
    if result.datasets:
        _console.print("\n[bold]Datasets:[/bold]")
        table = Table(show_header=True)
        table.add_column("Dataset", style="cyan")
        table.add_column("Profile", style="green")
        table.add_column("Mount", style="blue")
        table.add_column("Est. Size", style="dim")

        for ds in result.datasets:
            table.add_row(
                ds.name,
                ds.profile,
                ds.mount_point,
                ds.size_estimate
            )
        _console.print(table)

    # Generate YAML
    yaml_config = converter.to_yaml(result)

    # Show preview if requested
    if show_preview and not output:
        _console.print("\n[bold]Generated Configuration:[/bold]\n")
        _console.print(yaml_config)

    # Save to file if output specified
    if output:
        output_path = Path(output)
        try:
            output_path.write_text(yaml_config)
            print_success(_console, f"Saved config to {output}")

            if result.secrets_needed:
                _console.print("\n[yellow]⚠️  Remember to set these secrets in the config:[/yellow]")
                for secret in result.secrets_needed:
                    _console.print(f"  - {secret}")

            _console.print("\n[dim]Next steps:[/dim]")
            _console.print(f"  1. Review and edit: {output}")
            _console.print(f"  2. Preview changes: tg diff --config {output}")
            _console.print(f"  3. Deploy: tg apply --config {output}")

        except Exception as exc:
            print_error(_console, f"Failed to write {output}: {exc}")
            raise typer.Exit(1) from exc
    elif not show_preview:
        # No output file and no preview = user gets nothing
        print_warning(_console, "No output file specified. Use --output to save config.")
        _console.print("\n[dim]Run again with --output tengil.yml to save the configuration[/dim]")
