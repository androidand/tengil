"""Utility CLI commands - suggest, doctor, version."""
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tengil.recommendations import show_all_recommendations, show_dataset_recommendations

# Module-level console instance (will be set by register function)
console: Console = Console()


def suggest(
    dataset_type: Optional[str] = typer.Argument(None, help="Dataset type (media, photos, backups, etc.)")
):
    """Suggest LXC containers for dataset types.

    Examples:
        tg suggest              # Show all recommendations
        tg suggest media        # Show media server options
        tg suggest photos       # Show photo management options
    """
    if dataset_type:
        if not show_dataset_recommendations(dataset_type, console):
            raise typer.Exit(1)
    else:
        show_all_recommendations(console)


def doctor(
    save: bool = typer.Option(False, "--save", help="Save system info to ~/.tengil/system.json"),
):
    """Show system hardware and software information.

    Detects CPU, GPU, memory, storage, network, and OS details.
    Useful for troubleshooting and understanding what Tengil can work with.
    """
    from tengil.discovery.hwdetect import SystemDetector

    console.print("\n[bold cyan]🔍 System Detection[/bold cyan]\n")

    detector = SystemDetector()
    facts = detector.detect_all()

    # CPU Info
    cpu = facts['cpu']
    console.print(Panel(
        f"[bold]Model:[/bold] {cpu['model']}\n"
        f"[bold]Cores:[/bold] {cpu['cores']}\n"
        f"[bold]Threads:[/bold] {cpu['threads']}",
        title="💻 CPU",
        border_style="blue"
    ))

    # GPU Info
    gpus = facts['gpu']
    if gpus:
        gpu_info = "\n".join([
            f"[bold]{gpu['type'].upper()}:[/bold] {gpu['model']}" +
            (f" (Driver: {gpu['driver']})" if 'driver' in gpu else "")
            for gpu in gpus
        ])
        console.print(Panel(
            gpu_info,
            title="🎮 GPU",
            border_style="green"
        ))
    else:
        console.print(Panel(
            "[dim]No GPU detected[/dim]",
            title="🎮 GPU",
            border_style="yellow"
        ))

    # Memory Info
    memory = facts['memory']
    console.print(Panel(
        f"[bold]Total:[/bold] {memory['total_gb']} GB",
        title="🧠 Memory",
        border_style="magenta"
    ))

    # Storage Info
    storage = facts['storage']
    if storage:
        table = Table(title="💾 ZFS Pools", show_header=True)
        table.add_column("Pool", style="cyan")
        table.add_column("Size", style="blue")
        table.add_column("Allocated", style="yellow")
        table.add_column("Free", style="green")
        table.add_column("Health", style="bold")

        for pool in storage:
            health_color = "green" if pool['health'] == 'ONLINE' else "red"
            table.add_row(
                pool['name'],
                pool['size'],
                pool['alloc'],
                pool['free'],
                f"[{health_color}]{pool['health']}[/{health_color}]"
            )

        console.print(table)
    else:
        console.print(Panel(
            "[dim]No ZFS pools detected[/dim]",
            title="💾 Storage",
            border_style="yellow"
        ))

    # Network Info
    network = facts['network']
    if network:
        net_info = "\n".join([
            f"[bold]{iface['name']}:[/bold] " +
            ("[green]UP[/green]" if iface['up'] else "[red]DOWN[/red]")
            for iface in network
        ])
        console.print(Panel(
            net_info,
            title="🌐 Network",
            border_style="cyan"
        ))

    # OS Info
    os_info = facts['os']
    console.print(Panel(
        f"[bold]OS:[/bold] {os_info['name']}\n"
        f"[bold]Kernel:[/bold] {os_info['kernel']}",
        title="🐧 Operating System",
        border_style="blue"
    ))

    # Save if requested
    if save:
        path = detector.save_state()
        from tengil.cli_support import print_success
        print_success(console, f"System info saved to: {path}")
    else:
        console.print("\n[dim]Tip: Use --save to store this info in ~/.tengil/system.json[/dim]")

    console.print()


def version():
    """Show Tengil version."""
    console.print("Tengil v0.1.0 - The Overlord of Your Homelab")


def register_utility_commands(
    app: typer.Typer,
    shared_console: Console,
    shared_template_loader=None
):
    """Register utility commands with the main Typer app.

    Args:
        app: Main Typer application
        shared_console: Shared Rich console instance
        shared_template_loader: Not used here, for API consistency
    """
    global console
    console = shared_console

    # Register commands
    app.command()(suggest)
    app.command()(doctor)
    app.command()(version)
