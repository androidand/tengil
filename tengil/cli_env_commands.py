"""Environment variable management commands for Tengil CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from tengil.cli_support import (
    get_container_orchestrator,
    print_error,
    print_success,
    resolve_container,
)

env_app = typer.Typer(help="Manage container environment variables", add_completion=False)
_ENV_APP_ATTACHED = False
console = Console()


def register_env_commands(app: typer.Typer, shared_console: Console) -> None:
    """Attach env subcommands to the main Typer app."""
    global console, _ENV_APP_ATTACHED
    console = shared_console

    if not _ENV_APP_ATTACHED:
        app.add_typer(env_app, name="env")
        _ENV_APP_ATTACHED = True


@env_app.command("list")
def env_list(
    container: str = typer.Argument(..., help="Container name or VMID"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    show_values: bool = typer.Option(False, "--show-values", help="Show environment variable values"),
) -> None:
    """List environment variables for a container."""
    orchestrator = get_container_orchestrator()

    vmid, display_name = resolve_container(container, orchestrator, console)

    console.print(f"[cyan]Environment variables for {display_name} (vmid {vmid}):[/cyan]")

    if show_values:
        cmd = "printenv | sort | grep -v -E '(TOKEN|PASSWORD|SECRET|KEY)=' || true"
    else:
        cmd = "printenv | cut -d= -f1 | sort"

    orchestrator.exec_container_command(vmid=vmid, command=["bash", "-c", cmd])


@env_app.command("set")
def env_set(
    container: str = typer.Argument(..., help="Container name or VMID"),
    variable: str = typer.Argument(..., help="Environment variable name"),
    value: str = typer.Argument(..., help="Environment variable value"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    restart_service: Optional[str] = typer.Option(None, "--restart", help="Service to restart after setting variable"),
) -> None:
    """Set an environment variable in a container."""
    orchestrator = get_container_orchestrator()
    vmid, display_name = resolve_container(container, orchestrator, console)

    console.print(f"[cyan]Setting {variable} in {display_name}...[/cyan]")

    update_cmd = f"""
    ENV_FILE="/app/.env"
    if [ ! -f "$ENV_FILE" ]; then
        touch "$ENV_FILE"
        chmod 600 "$ENV_FILE"
    fi

    grep -v "^{variable}=" "$ENV_FILE" > "$ENV_FILE.tmp" 2>/dev/null || true
    echo "{variable}={value}" >> "$ENV_FILE.tmp"
    mv "$ENV_FILE.tmp" "$ENV_FILE"
    echo "✓ Set {variable} in $ENV_FILE"
    """

    exit_code = orchestrator.exec_container_command(vmid=vmid, command=["bash", "-c", update_cmd])

    if exit_code == 0:
        print_success(console, f"Set {variable} in {display_name}")
        if restart_service:
            console.print(f"[cyan]Restarting {restart_service}...[/cyan]")
            restart_exit = orchestrator.exec_container_command(
                vmid=vmid, command=["systemctl", "restart", restart_service]
            )
            if restart_exit == 0:
                print_success(console, f"Restarted {restart_service}")
            else:
                print_error(console, f"Failed to restart {restart_service}")
    else:
        print_error(console, f"Failed to set {variable}")
        raise typer.Exit(1)


@env_app.command("sync")
def env_sync(
    container: str = typer.Argument(..., help="Container name or VMID"),
    env_file: str = typer.Argument(..., help="Local .env file to sync"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    restart_service: Optional[str] = typer.Option(None, "--restart", help="Service to restart after sync"),
) -> None:
    """Sync a local .env file into the container."""
    env_path = Path(env_file)
    if not env_path.exists():
        print_error(console, f"Environment file not found: {env_file}")
        raise typer.Exit(1)

    orchestrator = get_container_orchestrator()
    vmid, display_name = resolve_container(container, orchestrator, console)

    console.print(f"[cyan]Syncing {env_file} to {display_name}...[/cyan]")

    env_content = env_path.read_text()
    write_cmd = f"""
    cat > /app/.env << 'EOF'
{env_content}EOF
    chmod 600 /app/.env
    echo "✓ Synced environment file"
    """

    exit_code = orchestrator.exec_container_command(vmid=vmid, command=["bash", "-c", write_cmd])

    if exit_code == 0:
        print_success(console, f"Synced environment to {display_name}")
        if restart_service:
            console.print(f"[cyan]Restarting {restart_service}...[/cyan]")
            restart_exit = orchestrator.exec_container_command(
                vmid=vmid, command=["systemctl", "restart", restart_service]
            )
            if restart_exit == 0:
                print_success(console, f"Restarted {restart_service}")
            else:
                print_error(console, f"Failed to restart {restart_service}")
    else:
        print_error(console, "Failed to sync environment")
        raise typer.Exit(1)
