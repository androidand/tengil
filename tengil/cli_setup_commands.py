"""Setup CLI commands - init, add, repo, import."""
import os
import subprocess
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console

from tengil.core.importer import InfrastructureImporter
from tengil.core.package_loader import PackageLoader
from tengil.core.template_loader import TemplateLoader

# Module-level instances (will be set by register function)
console: Console = Console()
template_loader: TemplateLoader = TemplateLoader()
repo_app = typer.Typer(help="Git repository helpers")


def add(
    app_name: str = typer.Argument(..., help="App to add (e.g., jellyfin, pihole, nextcloud)"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    pool: Optional[str] = typer.Option(None, "--pool", "-p", help="Pool to use (auto-detect if not specified)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Add an app to existing config (e.g., 'tg add jellyfin').

    This command makes it easy to add common apps to your existing tengil.yml.
    It will create an optimized dataset, configure the container, and optionally
    set up shares - all with best practices built-in.

    Examples:
        tg add jellyfin          # Add Jellyfin media server
        tg add pihole            # Add Pi-hole DNS blocker
        tg add nextcloud -p tank # Add Nextcloud to specific pool
    """
    from tengil.cli_support import print_warning

    print_warning(console, "The 'add' command is coming soon!")
    console.print("\nFor now, use:")
    console.print(f"  [cyan]tg init --package {app_name}[/cyan]  # Start fresh config")
    console.print(f"\nOr manually edit tengil.yml to add {app_name}")
    console.print("\n💡 This feature will let you add apps to existing configs seamlessly.")
    raise typer.Exit(0)


def init(
    template: Optional[str] = typer.Option(None, "--template", "-t",
                                          help="Template name (e.g., homelab, media-server)"),
    templates: Optional[str] = typer.Option(None, "--templates",
                                           help="Comma-separated templates to combine"),
    datasets: Optional[str] = typer.Option(None, "--datasets",
                                          help="Comma-separated dataset names to include"),
    package: Optional[str] = typer.Option(None, "--package", "-P",
                                         help="Package name (e.g., media-server, nas-complete)"),
    pool: str = typer.Option("tank", "--pool", "-p", help="ZFS pool name"),
    list_templates: bool = typer.Option(False, "--list-templates", help="List available templates"),
    list_datasets: bool = typer.Option(False, "--list-datasets", help="List available datasets"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Skip prompts, use defaults")
):
    """Initialize a new tengil.yml from a preset package.

    This is the fastest way to get started. Choose a package that matches
    your use case, and Tengil generates an optimized configuration.

    Examples:
        tg init --template homelab                  # Use homelab template
        tg init --templates homelab,media-server    # Combine multiple templates
        tg init --datasets movies,tv,photos         # Select specific datasets
        tg init --package media-server              # Use preset package (interactive)
        tg init --package nas-complete --non-interactive  # Use package with defaults
    """
    from tengil.cli_support import print_success

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
        config_path = Path.home() / "tengil-configs" / "tengil.yml"
    if config_path.exists():
        console.print("[yellow]Warning:[/yellow] tengil.yml already exists")
        if not typer.confirm("Overwrite?"):
            return

    try:
        configs_to_merge = []

        # Load from --package flag (preset packages)
        if package:
            console.print(f"[cyan]Loading package:[/cyan] {package}\n")

            package_loader = PackageLoader()
            pkg = package_loader.load_package(package)

            # Show package info
            console.print(f"[bold]{pkg.name}[/bold]")
            console.print(f"{pkg.description}\n")

            if pkg.components:
                console.print("[dim]Components:[/dim]")
                for comp in pkg.components:
                    console.print(f"  • {comp}")
                console.print()

            # Collect user inputs
            user_inputs = {"pool_name": pool}  # Default pool name

            if pkg.prompts and not non_interactive:
                console.print("[bold]Customization:[/bold]")
                for prompt in pkg.prompts:
                    # Show prompt with default
                    default_display = f" [{prompt.default}]" if prompt.default is not None else ""
                    user_input = typer.prompt(
                        f"  {prompt.prompt}{default_display}",
                        default=prompt.default if prompt.default is not None else "",
                        show_default=False
                    )

                    # Type conversion
                    if prompt.type == "int":
                        user_inputs[prompt.id] = int(user_input) if user_input else prompt.default
                    elif prompt.type == "bool":
                        # Handle empty input (use default) and string conversion
                        if user_input == "" or user_input is None:
                            user_inputs[prompt.id] = prompt.default
                        elif isinstance(user_input, bool):
                            user_inputs[prompt.id] = user_input
                        else:
                            user_inputs[prompt.id] = str(user_input).lower() in ['true', 'yes', 'y', '1']
                    else:
                        user_inputs[prompt.id] = user_input if user_input else prompt.default

                console.print()
            elif pkg.prompts and non_interactive:
                # Use defaults for all prompts
                console.print("[dim]Using default values for all prompts[/dim]\n")
                for prompt in pkg.prompts:
                    user_inputs[prompt.id] = prompt.default

            # Check if this is a Docker Compose package
            if pkg.docker_compose:
                console.print("[cyan]📦 Docker Compose integration detected[/cyan]")
                console.print("[dim]Analyzing compose file...[/dim]\n")

                # Generate config from Docker Compose
                final_config = package_loader.render_compose_config(pkg, user_inputs)

                print_success(console, "Generated config from Docker Compose + Tengil opinions")
                console.print(f"[dim]  Datasets: {len(final_config['pools'][pool]['datasets'])}[/dim]")
            else:
                # Traditional package with embedded config
                # Render package config with user inputs
                final_config = package_loader.render_config(pkg, user_inputs)

        # Load from --datasets flag
        elif datasets:
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

        # Process non-package configs
        if not package:
            # Merge all configurations
            merged_config = template_loader.merge_configs(configs_to_merge)

            # Substitute ${pool} variable
            final_config = template_loader.substitute_pool(merged_config, pool)

        # Write configuration
        with open(config_path, 'w') as f:
            yaml.dump(final_config, f, default_flow_style=False, sort_keys=False)

        print_success(console, f"Created {config_path}")
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print("  1. Edit tengil.yml to customize your setup")
        console.print("  2. Run 'tg diff' to see what changes will be made")
        console.print("  3. Run 'tg apply' to apply the configuration")

    except FileNotFoundError as err:
        console.print(f"[red]Error:[/red] {err}")
        if package:
            console.print("\n[dim]Use 'tg packages list' to see available packages[/dim]")
        else:
            console.print("\nAvailable templates:")
            for t in template_loader.list_templates():
                console.print(f"  • {t}")
            console.print("\nAvailable datasets:")
            for d in template_loader.list_datasets():
                console.print(f"  • {d}")
        raise typer.Exit(1) from err
    except Exception as err:
        console.print(f"[red]Error:[/red] {err}")
        raise typer.Exit(1) from err


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
    from tengil.cli_support import print_error, print_success

    console.print("[bold cyan]Tengil Import[/bold cyan]")
    console.print(f"Scanning pool: [yellow]{pool}[/yellow]\n")

    mock = os.environ.get('TG_MOCK') == '1' or dry_run
    importer = InfrastructureImporter(mock=mock)

    # Generate configuration
    config = importer.generate_config(pool)

    # Show summary
    print_success(console, f"Found {len(config['datasets'])} dataset(s)")
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
            print_success(console, f"Wrote configuration to: {output}")
            console.print("\n[yellow]Next steps:[/yellow]")
            console.print(f"  1. Review: cat {output}")
            console.print("  2. Edit profiles and add any missing containers")
            console.print(f"  3. Apply: tg apply --config {output}")
        else:
            print_error(console, "Failed to write configuration")
            raise typer.Exit(1)


@repo_app.command("init")
def repo_init(
    path: str = typer.Option(str(Path.home() / "tengil-configs"), "--path", "-p", help="Directory to initialize the repo in"),
    force: bool = typer.Option(False, "--force", "-f", help="Reinitialize even if .git already exists"),
    skip_gitignore: bool = typer.Option(False, "--skip-gitignore", help="Do not create/update .gitignore"),
):
    """Initialize a Git repository for Tengil config + create a sensible .gitignore."""
    target = Path(path).expanduser()
    target.mkdir(parents=True, exist_ok=True)

    git_dir = target / ".git"
    if git_dir.exists() and not force:
        console.print(f"[yellow]Git repo already exists in {target}[/yellow]")
        console.print("Use --force to reinitialize.")
        raise typer.Exit(0)

    try:
        subprocess.run(["git", "init"], cwd=str(target), check=True, capture_output=True)
    except FileNotFoundError:
        console.print("[red]Git executable not found. Install git and retry.[/red]")
        raise typer.Exit(1)
    except subprocess.CalledProcessError as exc:
        console.print(f"[red]git init failed:[/red] {exc.stderr.decode().strip() if exc.stderr else exc}")
        raise typer.Exit(1)

    gitignore = target / ".gitignore"
    if not skip_gitignore:
        entries = [
            "# Tengil defaults",
            ".tengil/",
            "*.log",
            "*.tmp",
            "__pycache__/",
            ".DS_Store",
            "compose_cache/",
        ]
        gitignore.write_text("\n".join(entries) + "\n")

    console.print(f"[green]✓[/green] Initialized Git repo in {target}")
    if not skip_gitignore:
        console.print(f"[green]✓[/green] Wrote {gitignore.relative_to(target)}")

    suggested = target / "tengil.yml"
    if not suggested.exists():
        console.print(f"[yellow]Note:[/yellow] {suggested} does not exist yet. Run 'tg init' or copy your config.")

    console.print("\nNext steps:")
    console.print(f"  cd {target}")
    console.print("  git add tengil.yml")
    console.print("  git commit -m \"Initial Tengil config\"")


def register_setup_commands(
    app: typer.Typer,
    shared_console: Console,
    shared_template_loader: Optional[TemplateLoader] = None
):
    """Register setup commands with the main Typer app.

    Args:
        app: Main Typer application
        shared_console: Shared Rich console instance
        shared_template_loader: Preconfigured template loader from main CLI
    """
    global console
    global template_loader
    console = shared_console

    if shared_template_loader is not None:
        template_loader = shared_template_loader

    # Register commands
    app.command()(init)
    app.command()(add)
    app.command(name="import")(import_config)
    repo_app.command("init")(repo_init)
    app.add_typer(repo_app, name="repo")
