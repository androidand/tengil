"""Container helper CLI commands."""
from __future__ import annotations

from typing import Dict, List, Optional

import typer
from rich.console import Console

from tengil.cli_container_resolution import ContainerResolutionError, resolve_container_target
from tengil.cli_support import is_mock
from tengil.services.proxmox.containers import ContainerOrchestrator
from tengil.services.proxmox.backends.lxc import LXCBackend
from tengil.services.proxmox.containers.lifecycle import ContainerLifecycle

ContainerTyper = typer.Typer(help="Interact with Proxmox containers")


def register_container_commands(root: typer.Typer, console: Console) -> None:
    """Attach container-related commands to the main CLI."""

    @ContainerTyper.command("exec")
    def exec_command(
        target: str = typer.Argument(..., help="Container target (name, vmid, or pool/dataset:name)."),
        command: List[str] = typer.Argument(..., help="Command to run inside the container.", metavar="COMMAND..."),
        user: Optional[str] = typer.Option(None, "--user", "-u", help="Run command as specific user inside the container."),
        env: Optional[List[str]] = typer.Option(None, "--env", "-e", help="Environment variable (KEY=VALUE).", metavar="KEY=VALUE"),
        workdir: Optional[str] = typer.Option(None, "--workdir", "-w", help="Working directory inside the container."),
        config: Optional[str] = typer.Option(None, "--config", "-c", help="Explicit Tengil config for dataset resolution."),
    ) -> None:
        if not command:
            console.print("[red]Error:[/red] Provide a command to execute.")
            raise typer.Exit(2)

        try:
            resolved = resolve_container_target(target, config_path=config)
        except ContainerResolutionError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(2) from exc

        env_dict: Dict[str, str] = {}
        if env:
            for item in env:
                if "=" not in item:
                    raise typer.BadParameter("Environment variables must be KEY=VALUE", param_name="env")
                key, value = item.split("=", 1)
                env_dict[key] = value

        lifecycle = ContainerLifecycle(mock=is_mock())
        result = lifecycle.exec_container_command(
            resolved.vmid,
            command,
            user=user,
            env=env_dict,
            workdir=workdir,
        )

        if result != 0:
            raise typer.Exit(result)

    @ContainerTyper.command("shell")
    def shell_command(
        target: str = typer.Argument(..., help="Container target (name, vmid, or pool/dataset:name)."),
        user: Optional[str] = typer.Option(None, "--user", "-u", help="User for the interactive shell."),
        config: Optional[str] = typer.Option(None, "--config", "-c", help="Explicit Tengil config for dataset resolution."),
    ) -> None:
        """Open an interactive shell in the container."""
        try:
            resolved = resolve_container_target(target, config_path=config)
        except ContainerResolutionError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(2) from exc

        lifecycle = ContainerLifecycle(mock=is_mock())
        result = lifecycle.enter_container_shell(resolved.vmid, user=user)
        if result != 0:
            raise typer.Exit(result)

    @ContainerTyper.command("start")
    def start_command(
        target: str = typer.Argument(..., help="Container target (name, vmid, or pool/dataset:name)."),
        config: Optional[str] = typer.Option(None, "--config", "-c", help="Explicit Tengil config for dataset resolution."),
    ) -> None:
        """Start a stopped container."""
        from tengil.cli_support import print_success, print_error

        try:
            resolved = resolve_container_target(target, config_path=config)
        except ContainerResolutionError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(2) from exc

        console.print(f"[dim]Starting container {resolved.name} (VMID {resolved.vmid})...[/dim]")

        lifecycle = ContainerLifecycle(mock=is_mock())
        success = lifecycle.start_container(resolved.vmid)

        if success:
            print_success(console, f"Started {resolved.name}")
        else:
            print_error(console, f"Failed to start {resolved.name}")
            raise typer.Exit(1)

    @ContainerTyper.command("stop")
    def stop_command(
        target: str = typer.Argument(..., help="Container target (name, vmid, or pool/dataset:name)."),
        config: Optional[str] = typer.Option(None, "--config", "-c", help="Explicit Tengil config for dataset resolution."),
    ) -> None:
        """Stop a running container."""
        from tengil.cli_support import print_success, print_error

        try:
            resolved = resolve_container_target(target, config_path=config)
        except ContainerResolutionError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(2) from exc

        console.print(f"[dim]Stopping container {resolved.name} (VMID {resolved.vmid})...[/dim]")

        lifecycle = ContainerLifecycle(mock=is_mock())
        success = lifecycle.stop_container(resolved.vmid)

        if success:
            print_success(console, f"Stopped {resolved.name}")
        else:
            print_error(console, f"Failed to stop {resolved.name}")
            raise typer.Exit(1)

    @ContainerTyper.command("restart")
    def restart_command(
        target: str = typer.Argument(..., help="Container target (name, vmid, or pool/dataset:name)."),
        config: Optional[str] = typer.Option(None, "--config", "-c", help="Explicit Tengil config for dataset resolution."),
    ) -> None:
        """Restart a container."""
        from tengil.cli_support import print_success, print_error

        try:
            resolved = resolve_container_target(target, config_path=config)
        except ContainerResolutionError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(2) from exc

        console.print(f"[dim]Restarting container {resolved.name} (VMID {resolved.vmid})...[/dim]")

        lifecycle = ContainerLifecycle(mock=is_mock())
        success = lifecycle.restart_container(resolved.vmid)

        if success:
            print_success(console, f"Restarted {resolved.name}")
        else:
            print_error(console, f"Failed to restart {resolved.name}")
            raise typer.Exit(1)

    @ContainerTyper.command("update")
    def update_command(
        target: str = typer.Argument(..., help="Container target (name, vmid, or pool/dataset:name)."),
        no_upgrade: bool = typer.Option(False, "--no-upgrade", help="Only run apt update, skip apt upgrade."),
        config: Optional[str] = typer.Option(None, "--config", "-c", help="Explicit Tengil config for dataset resolution."),
    ) -> None:
        """Update packages in a container (apt update && apt upgrade).

        By default, runs both apt update and apt upgrade.
        Use --no-upgrade to only update package lists without upgrading.
        """
        from tengil.cli_support import print_success, print_error

        try:
            resolved = resolve_container_target(target, config_path=config)
        except ContainerResolutionError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(2) from exc

        upgrade = not no_upgrade
        action = "Updating and upgrading" if upgrade else "Updating"
        console.print(f"[dim]{action} packages in {resolved.name} (VMID {resolved.vmid})...[/dim]")

        lifecycle = ContainerLifecycle(mock=is_mock())
        success = lifecycle.update_container(resolved.vmid, upgrade=upgrade)

        if success:
            msg = f"Updated and upgraded {resolved.name}" if upgrade else f"Updated package lists in {resolved.name}"
            print_success(console, msg)
        else:
            print_error(console, f"Failed to update {resolved.name}")
            raise typer.Exit(1)

    @ContainerTyper.command("launch")
    def launch_command(
        name: str = typer.Argument(..., help="Container name/hostname."),
        vmid: Optional[int] = typer.Option(None, "--vmid", help="VMID (optional, auto-alloc if omitted)."),
        type_: str = typer.Option("oci", "--type", case_sensitive=False, help="Container type: oci or lxc (default: oci)."),
        image: Optional[str] = typer.Option(None, "--image", help="OCI image (e.g., docker.io/library/nginx:latest)."),
        template: Optional[str] = typer.Option(None, "--template", help="LXC template (e.g., debian-12-standard)."),
        storage: str = typer.Option("local-lvm", "--storage", help="Rootfs storage (default: local-lvm)."),
        pool: Optional[str] = typer.Option(None, "--pool", help="Proxmox pool to assign (optional)."),
        env: List[str] = typer.Option(None, "--env", "-e", help="Environment variable (KEY=VALUE).", metavar="KEY=VALUE"),
    ) -> None:
        """Launch a simple container with optional env vars (one-shot create)."""
        from tengil.cli_support import print_success, print_error

        env_dict: Dict[str, str] = {}
        for item in env or []:
            if "=" not in item:
                raise typer.BadParameter("Environment variables must be KEY=VALUE", param_name="env")
            key, value = item.split("=", 1)
            env_dict[key] = value

        spec: Dict[str, object] = {
            "name": name,
            "hostname": name,
            "vmid": vmid,
            "env": env_dict,
        }

        is_oci = type_.lower() == "oci"
        if is_oci:
            if not image:
                console.print("[red]Error:[/red] --image is required for OCI launch")
                raise typer.Exit(2)
            spec["type"] = "oci"
            spec["oci"] = {"image": image}
        else:
            if not template:
                console.print("[red]Error:[/red] --template is required for LXC launch")
                raise typer.Exit(2)
            spec["type"] = "lxc"
            spec["template"] = template

        orch = ContainerOrchestrator(mock=is_mock())
        vmid_result = orch.create_container(spec, storage=storage, pool=pool)

        if not vmid_result:
            print_error(console, f"Failed to launch {name}")
            raise typer.Exit(1)

        # Ensure env is persisted (especially for LXC which may need pct set)
        orch._apply_env(vmid_result, spec, name)

        print_success(console, f"Launched {name} (vmid={vmid_result})")

    @ContainerTyper.command("env")
    def env_set_command(
        target: str = typer.Argument(..., help="Container target (name, vmid, or pool/dataset:name)."),
        env: List[str] = typer.Option(..., "--env", "-e", help="Environment variable (KEY=VALUE).", metavar="KEY=VALUE"),
        no_restart: bool = typer.Option(False, "--no-restart", help="Do not restart the container after applying env."),
        config: Optional[str] = typer.Option(None, "--config", "-c", help="Explicit Tengil config for dataset resolution."),
    ) -> None:
        """Set persistent environment variables on a container (uses pct set --env)."""
        from tengil.cli_support import print_success, print_error

        try:
            resolved = resolve_container_target(target, config_path=config)
        except ContainerResolutionError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(2) from exc

        env_dict: Dict[str, str] = {}
        for item in env:
            if "=" not in item:
                raise typer.BadParameter("Environment variables must be KEY=VALUE", param_name="env")
            key, value = item.split("=", 1)
            env_dict[key] = value

        backend = LXCBackend(mock=is_mock())
        if not backend.update_env(resolved.vmid, env_dict):
            print_error(console, f"Failed to update env for {resolved.name}")
            raise typer.Exit(1)

        if not no_restart:
            lifecycle = ContainerLifecycle(mock=is_mock())
            lifecycle.restart_container(resolved.vmid)

        print_success(console, f"Updated env for {resolved.name} ({resolved.vmid})")

    root.add_typer(ContainerTyper, name="container")
