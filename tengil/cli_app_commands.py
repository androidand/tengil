"""Application-related CLI commands."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import typer
import yaml
from rich.console import Console

from tengil.cli_container_resolution import ContainerResolutionError, resolve_container_target
from tengil.cli_support import is_mock
from tengil.services.git_manager import GitManager

AppTyper = typer.Typer(help="Manage application repositories inside containers")


def register_app_commands(root: typer.Typer, console: Console) -> None:
    """Attach app subcommands to the main CLI."""

    @AppTyper.command("sync")
    def sync_command(
        target: Optional[str] = typer.Argument(None, help="Container target (name, vmid, or pool/dataset:name)."),
        repo: Optional[str] = typer.Argument(None, help="Git repository URL."),
        path: Optional[str] = typer.Option(None, "--path", "-p", help="Destination directory inside the container."),
        branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Repository branch (default: main)."),
        spec: Optional[Path] = typer.Option(None, "--spec", help="Load defaults from repo spec YAML."),
        config: Optional[str] = typer.Option(None, "--config", "-c", help="Explicit Tengil config for dataset resolution."),
    ) -> None:
        """Clone or update an application repository inside a container."""
        spec_data = _load_spec(spec) if spec else {}

        target_value = target or spec_data.get("target")
        repo_value = repo or spec_data.get("repo")
        branch_value = branch or spec_data.get("branch") or "main"
        path_value = path or spec_data.get("path")
        config_value = config or spec_data.get("config")

        if not target_value or not repo_value:
            console.print("[red]Error:[/red] Provide target and repo (arguments or spec).")
            raise typer.Exit(2)

        if not path_value:
            path_value = _default_repo_path(repo_value)

        try:
            resolved = resolve_container_target(target_value, config_path=config_value)
        except ContainerResolutionError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(2) from exc

        git = GitManager(mock=is_mock())

        console.print(f"[dim]Target container:[/dim] {resolved.name} (vmid={resolved.vmid})")
        destination = str(Path(path_value))
        parent_dir = str(Path(destination).parent)

        if git.repo_exists(resolved.vmid, destination):
            console.print(f"Pulling latest changes in {destination}...")
            if not git.pull_repo(resolved.vmid, destination):
                raise typer.Exit(1)
            console.print("[green]✓ Repository updated[/green]")
            return

        if not git.ensure_directory(resolved.vmid, parent_dir):
            raise typer.Exit(1)

        console.print(f"Cloning {repo_value} (branch: {branch_value}) → {destination}")
        if not git.clone_repo(resolved.vmid, repo_value, destination, branch=branch_value):
            raise typer.Exit(1)
        console.print("[green]✓ Repository cloned[/green]")

    @AppTyper.command("list")
    def list_command(
        target: Optional[str] = typer.Argument(None, help="Container target (name, vmid, or pool/dataset:name)."),
        spec: Optional[Path] = typer.Option(None, "--spec", help="Load defaults from repo spec YAML."),
        root: Optional[str] = typer.Option(None, "--root", help="Manifest search root inside the container."),
        pattern: Optional[str] = typer.Option(None, "--glob", help="Glob pattern for manifests (default: *.yml)."),
        depth: Optional[int] = typer.Option(None, "--depth", help="Max directory depth for manifest discovery."),
        config: Optional[str] = typer.Option(None, "--config", "-c", help="Explicit Tengil config for dataset resolution."),
    ) -> None:
        """List app manifests stored inside a container repository."""
        spec_data = _load_spec(spec) if spec else {}

        target_value = target or spec_data.get("target")
        if not target_value:
            console.print("[red]Error:[/red] Target container is required (argument or spec).")
            raise typer.Exit(2)

        manifests_cfg: Dict[str, object] = spec_data.get("manifests", {}) if spec_data else {}
        root_value = root or manifests_cfg.get("root")
        pattern_value = pattern or manifests_cfg.get("glob") or "*.yml"
        depth_value = depth or manifests_cfg.get("depth") or 3
        config_value = config or spec_data.get("config")

        repo_path = spec_data.get("path")
        repo_value = spec_data.get("repo")
        if not root_value:
            assumed_base = repo_path or _default_repo_path(repo_value) if repo_value else None
            if assumed_base:
                root_value = str(Path(assumed_base) / "manifests")

        if not root_value:
            console.print("[red]Error:[/red] Unable to determine manifest root.")
            raise typer.Exit(2)

        try:
            resolved = resolve_container_target(target_value, config_path=config_value)
        except ContainerResolutionError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(2) from exc

        git = GitManager(mock=is_mock())
        manifest_paths = git.list_manifests(resolved.vmid, root_value, pattern_value, depth_value)

        count = len(manifest_paths)
        console.print(f"{count} manifest(s) found under {root_value}")
        if not manifest_paths:
            return

        for manifest_path in manifest_paths:
            rel_path = _relative_path(manifest_path, root_value)
            console.print(f"- {rel_path}")

            manifest_data = git.read_file(resolved.vmid, manifest_path) or ""
            details = _summarise_manifest(manifest_data)
            if details:
                for line in details:
                    console.print(f"    {line}")

    root.add_typer(AppTyper, name="app")


def _load_spec(spec_path: Path) -> Dict[str, object]:
    if not spec_path.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")
    data = yaml.safe_load(spec_path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError("Spec file must contain a mapping")
    return data


def _default_repo_path(repo: str) -> str:
    repo_name = repo.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    return f"/srv/apps/{repo_name}"


def _relative_path(path: str, root: str) -> str:
    try:
        return str(Path(path).relative_to(Path(root)))
    except ValueError:
        return path


def _summarise_manifest(content: str) -> List[str]:
    if not content:
        return []
    try:
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError:
        return ["(invalid manifest)"]

    if not isinstance(data, dict):
        return []

    lines: List[str] = []
    name = data.get("name")
    version = data.get("version")
    description = data.get("description")

    if name:
        label = str(name)
        if version:
            label += f" ({version})"
        lines.append(label)

    if description:
        lines.append(str(description))

    return lines
