"""Recovery CLI commands - snapshot, rollback."""
import typer
from rich.console import Console
from rich.table import Table

from tengil.cli_support import is_mock
from tengil.core.snapshot_manager import SnapshotManager
from tengil.core.state_store import StateStore

# Module-level console instance (will be set by register function)
console: Console = Console()


def snapshot(
    name: str = typer.Option(None, "--name", help="Snapshot name"),
    list_snapshots: bool = typer.Option(False, "--list", "-l", help="List snapshots"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Clean up old snapshots"),
    keep: int = typer.Option(5, help="Number of snapshots to keep")
):
    """Manage ZFS snapshots for rollback."""
    from tengil.cli_support import print_success, print_warning

    snapshot_manager = SnapshotManager(mock=is_mock())

    if list_snapshots:
        snapshots = snapshot_manager.list_snapshots()
        if not snapshots:
            print_warning(console, "No tengil snapshots found")
            return

        table = Table(title="Tengil Snapshots")
        table.add_column("Dataset", style="cyan")
        table.add_column("Snapshot", style="green")
        table.add_column("Created", style="yellow")
        table.add_column("Size", style="magenta")

        for snap in snapshots:
            table.add_row(
                snap['dataset'],
                snap['name'],
                snap['created'],
                snap['used']
            )

        console.print(table)

    elif cleanup:
        deleted = snapshot_manager.cleanup_old_snapshots(keep=keep)
        print_success(console, f"Deleted {deleted} old snapshot(s)")

    else:
        # Create snapshot of all managed datasets
        state = StateStore()
        datasets = list(state.state.get('datasets', {}).keys())

        if not datasets:
            print_warning(console, "No managed datasets found")
            return

        created = snapshot_manager.create_snapshot(datasets, name=name)
        print_success(console, f"Created {len(created)} snapshot(s)")
        for dataset, snap_name in created.items():
            console.print(f"  {dataset}@{snap_name}")


def rollback(
    dataset: str = typer.Argument(..., help="Dataset to rollback"),
    to: str = typer.Option(..., "--to", help="Snapshot name to rollback to"),
    force: bool = typer.Option(False, "--force", help="Force rollback (destroys newer snapshots)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Rollback dataset to snapshot (like 'terraform destroy', but safer)."""
    from tengil.cli_support import confirm_action, print_error, print_success, print_warning

    snapshot_manager = SnapshotManager(mock=is_mock())

    # Confirm unless --yes or mock mode
    if not confirm_action(f"Rollback {dataset} to {to}? This will destroy all changes after this snapshot.",
                         yes_flag=yes, mock=is_mock()):
        print_warning(console, "Cancelled")
        raise typer.Exit(0)

    if snapshot_manager.rollback(dataset, to, force=force):
        print_success(console, f"Rolled back {dataset} to {to}")
    else:
        print_error(console, f"Failed to rollback {dataset}")
        raise typer.Exit(1)


def register_recovery_commands(
    app: typer.Typer,
    shared_console: Console,
    shared_template_loader=None
):
    """Register recovery commands with the main Typer app.

    Args:
        app: Main Typer application
        shared_console: Shared Rich console instance
        shared_template_loader: Not used here, for API consistency
    """
    global console
    console = shared_console

    # Register commands
    app.command()(snapshot)
    app.command()(rollback)
