"""State management CLI commands - scan, diff, apply."""
import json
from pathlib import Path
from typing import List, Optional, Dict, Tuple

import typer
from rich.console import Console
from rich.table import Table

from tengil.cli_drift_helpers import analyze_drift
from tengil.cli_support import is_mock
from tengil.core.applicator import ChangeApplicator
from tengil.core.diff_engine import DiffEngine
from tengil.core.drift_engine import DriftEngine, DriftSeverity, summarize_drift_report
from tengil.core.permission_manager import PermissionManager
from tengil.core.recovery import RecoveryManager
from tengil.core.state_store import StateStore
from tengil.core.resource_validator import ResourceValidator, detect_host_resources
from tengil.core.zfs_manager import ZFSManager
from tengil.config.loader import ConfigLoader
from tengil.services.nas import NASManager
from tengil.services.proxmox import ProxmoxManager
from tengil.services.proxmox.state_collector import RealityStateCollector

# Module-level console instance (will be set by register function)
console: Console = Console()


def _show_drift_section(loader: Optional["ConfigLoader"]) -> None:
    """Render drift analysis comparing desired vs. last recorded reality."""
    from tengil.cli_support import print_info, print_success

    report, status = analyze_drift(loader)
    if report is None:
        if status == "missing-snapshot":
            print_info(console, "No reality snapshot found. Run 'tg scan' to capture current state.")
        elif status == "no-loader":
            pass
        elif status == "desired-error":
            print_info(console, "Unable to build desired-state model; skipping drift analysis.")
        return

    if report.is_clean():
        print_success(console, "Desired config matches last reality snapshot (no drift detected)")
        return

    _render_drift_report(report)


def _render_drift_report(report) -> None:
    """Print drift summary using Rich tables."""
    severity_labels = {
        DriftSeverity.DANGEROUS: "[red]Dangerous[/red]",
        DriftSeverity.AUTO_MERGE: "[yellow]Auto-merge[/yellow]",
        DriftSeverity.INFO: "[cyan]Info[/cyan]",
    }

    summary = summarize_drift_report(report)

    console.print("\n[bold magenta]Reality Drift Detected[/bold magenta]")
    summary_table = Table(show_header=True, header_style="bold")
    summary_table.add_column("Severity")
    summary_table.add_column("Count", justify="right")

    for severity, count in sorted(summary["counts"].items(), key=lambda item: item[0]):
        summary_table.add_row(
            severity_labels.get(severity, severity),
            str(count),
        )

    console.print(summary_table)

    if summary["samples"]:
        detail_table = Table(title="Sample Drift Items", show_header=True, header_style="bold cyan")
        detail_table.add_column("Severity")
        detail_table.add_column("Resource")
        detail_table.add_column("Field")
        detail_table.add_column("Message", overflow="fold")

        for item in summary["samples"]:
            detail_table.add_row(
                severity_labels.get(item["severity"], item["severity"]),
                item["resource"],
                item["field"],
                item["message"],
            )

        console.print(detail_table)
        console.print("[dim]Run 'tg scan' before making GUI changes to keep drift manageable.[/dim]")


def _validate_auto_create_resources(loader: ConfigLoader) -> None:
    """Warn/abort if auto-created containers exceed host resources."""
    processed_config = getattr(loader, "processed_config", None)
    if not processed_config:
        return

    host = detect_host_resources()
    if host.total_memory_mb <= 0:
        console.print("[yellow]Unable to detect host memory; skipping resource validation[/yellow]")
        return

    validator = ResourceValidator(processed_config, host)
    result = validator.validate()
    dataset_errors = _validate_host_paths(processed_config)
    if dataset_errors:
        console.print("[red]Dataset validation errors detected:[/red]")
        for err in dataset_errors:
            console.print(f"[red]✗ {err}[/red]")
        raise typer.Exit(1)

    if result.auto_create_count == 0:
        return

    console.print(
        f"[dim]Auto-create containers: {result.auto_create_count} "
        f"(RAM requested: {result.total_memory_mb} MB / host {host.total_memory_mb} MB, "
        f"cores requested: {result.total_cores} / host {host.total_cores})[/dim]"
    )

    for warning in result.warnings:
        console.print(f"[yellow]⚠ {warning}[/yellow]")

    if result.errors:
        console.print("[red]Auto-create resource requests exceed host capacity:[/red]")
        for error in result.errors:
            console.print(f"[red]✗ {error}[/red]")
        raise typer.Exit(1)


def _validate_host_paths(processed_config: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    pools = processed_config.get("pools", {})
    for pool_name, pool_cfg in pools.items():
        datasets: Dict[str, Dict[str, Any]] = pool_cfg.get("datasets", {})
        for dataset_name in datasets.keys():
            full_path = Path(f"/{pool_name}/{dataset_name}")
            if not full_path.exists():
                errors.append(f"{full_path} does not exist on the host. Run 'tg apply' to create datasets before mounting.")
    return errors


def scan(
    pools: List[str] = typer.Option([], "--pool", "-p", help="Limit scan to specific ZFS pools"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write reality snapshot to JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output"),
    save_state: bool = typer.Option(True, "--save-state/--no-save-state", help="Persist snapshot to Tengil state store"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Path to log file"),
):
    """Capture the current Proxmox + ZFS state into the Reality model."""
    from tengil.cli_support import (
        print_error,
        print_info,
        print_success,
        print_warning,
        setup_file_logging,
    )

    setup_file_logging(log_file=log_file, verbose=verbose)

    collector = RealityStateCollector(mock=is_mock())
    try:
        state = collector.collect(pools=pools or None)
    except Exception as exc:  # pragma: no cover - defensive
        print_error(console, f"Reality scan failed: {exc}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1) from exc

    metadata = state.get("metadata", {})
    container_data = state.get("containers", [])
    dataset_data = state.get("zfs", {}).get("datasets", {})

    console.print("[cyan]Reality snapshot captured[/cyan]")
    print_info(console, f"Generated at: {metadata.get('generated_at', 'unknown')}")
    print_info(console, f"Containers: {len(container_data)}")
    print_info(console, f"Pools scanned: {', '.join(dataset_data.keys()) or 'none'}")

    if container_data:
        table = Table(title="Containers", show_header=True, header_style="bold cyan")
        table.add_column("VMID", style="bold")
        table.add_column("Name")
        table.add_column("Status")
        table.add_column("Memory (MB)")
        table.add_column("Mounts")

        for container in container_data:
            resources = container.get("resources", {})
            memory = resources.get("memory_mb")
            mounts = container.get("mounts", [])
            table.add_row(
                str(container.get("vmid", "-")),
                container.get("name") or container.get("hostname") or "-",
                container.get("status", "unknown"),
                str(memory) if memory is not None else "-",
                str(len(mounts)),
            )

        console.print(table)
    else:
        print_warning(console, "No containers detected")

    if dataset_data:
        pool_table = Table(title="ZFS Datasets", show_header=True, header_style="bold cyan")
        pool_table.add_column("Pool")
        pool_table.add_column("Datasets")

        for pool_name, datasets in dataset_data.items():
            pool_table.add_row(pool_name, str(len(datasets)))

        console.print(pool_table)
    else:
        print_warning(console, "No ZFS datasets detected")

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state, indent=2 if pretty else None)
        output.write_text(payload)
        print_success(console, f"Reality snapshot saved to {output}")

    if save_state:
        store = StateStore()
        try:
            if store.should_track():
                snapshot_file = store.record_reality_snapshot(state)
                if snapshot_file is not None:
                    print_success(
                        console,
                        f"Reality snapshot recorded in state store ({snapshot_file})",
                    )
                else:
                    print_info(
                        console,
                        "Reality snapshot skipped (state store disabled)",
                    )
            else:
                print_info(console, "State store disabled in this environment; skipping persistence")
        except Exception as exc:  # pragma: no cover - defensive
            print_warning(console, f"Failed to record reality snapshot: {exc}")


def verify(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Path to log file"),
) -> None:
    """Validate configuration (parsing + resource checks) without running a diff/apply."""
    from tengil.cli_support import (
        handle_cli_error,
        load_config_and_orchestrate,
        print_success,
        setup_file_logging,
    )

    setup_file_logging(log_file=log_file, verbose=verbose)

    try:
        _loader, *_ = load_config_and_orchestrate(config, dry_run=True)
        _validate_auto_create_resources(_loader)
        print_success(console, "Configuration validated successfully")
    except FileNotFoundError as e:
        handle_cli_error(e, console, verbose, exit_code=1)
    except Exception as e:
        handle_cli_error(e, console, verbose, exit_code=1)


def diff(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Path to log file")
):
    """Show what changes would be made (like 'terraform plan').

    This command is read-only and does not make any changes to your infrastructure.
    Use 'tg apply' to actually apply the changes shown by this command.
    """
    from tengil.cli_support import (
        handle_cli_error,
        load_config_and_orchestrate,
        print_success,
        setup_file_logging,
    )

    # Set up file logging
    setup_file_logging(log_file=log_file, verbose=verbose)

    try:
        # Load configuration and set up orchestration (read-only mode)
        _loader, all_desired, all_current, container_mgr = load_config_and_orchestrate(config, dry_run=True)
        _validate_auto_create_resources(_loader)

        # Calculate diff across all pools (including containers)
        engine = DiffEngine(all_desired, all_current, container_manager=container_mgr)
        engine.calculate_diff()

        # Display plan
        if engine.changes or engine.container_changes:
            plan = engine.format_plan()
            console.print(plan)
        else:
            print_success(console, "All pools are up to date")
            _show_drift_section(_loader)
            return

        _show_drift_section(_loader)

    except FileNotFoundError as e:
        handle_cli_error(e, console, verbose, exit_code=1)
    except Exception as e:
        handle_cli_error(e, console, verbose, exit_code=1)


def apply(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show actions without applying"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Path to log file"),
    no_checkpoint: bool = typer.Option(False, "--no-checkpoint", help="Skip automatic checkpoint creation")
):
    """Apply the configuration (like 'terraform apply').

    Automatically creates a recovery checkpoint before applying changes.
    If apply fails, you can rollback using 'tg rollback'.
    """
    from tengil.cli_support import (
        confirm_action,
        load_config_and_orchestrate,
        print_error,
        print_success,
        print_warning,
        setup_file_logging,
    )

    # Set up file logging
    setup_file_logging(log_file=log_file, verbose=verbose)

    checkpoint = None
    recovery = None

    try:
        # Load configuration and set up orchestration
        _loader, all_desired, all_current, container_mgr = load_config_and_orchestrate(config, dry_run=dry_run)
        _validate_auto_create_resources(_loader)

        # Calculate diff across all pools (including containers)
        engine = DiffEngine(all_desired, all_current, container_manager=container_mgr)
        changes = engine.calculate_diff()

        if not changes and not engine.container_changes:
            print_success(console, "Infrastructure is up to date")
            _show_drift_section(_loader)
            return

        # Display plan
        plan = engine.format_plan()
        console.print(plan)

        drift_report, drift_status = analyze_drift(_loader)
        dangerous_drift = False
        if drift_report:
            if drift_report.is_clean():
                console.print("[dim]No drift detected compared to last scan.[/dim]")
            else:
                _render_drift_report(drift_report)
                dangerous_drift = any(item.severity == DriftSeverity.DANGEROUS for item in drift_report.items)
        elif drift_status == "missing-snapshot":
            console.print("[yellow]No reality snapshot found. Run 'tg scan' before relying on drift analysis.[/yellow]")
        elif drift_status == "desired-error":
            console.print("[yellow]Unable to compute drift (invalid desired-state data).[/yellow]")

        confirm_message = "\nDo you want to apply these changes?"
        if dangerous_drift:
            console.print("[red]Dangerous drift detected compared to last scan.[/red]")
            confirm_message = "\nDangerous drift detected. Continue with apply?"

        # Confirm unless --yes
        if not dry_run and not confirm_action(confirm_message, yes_flag=yes):
            print_warning(console, "Apply cancelled")
            return

        if dry_run:
            print_warning(console, "DRY RUN - No changes applied")
            return

        # Create recovery checkpoint before applying changes
        if not no_checkpoint:
            console.print("\n[dim]Creating recovery checkpoint...[/dim]")
            recovery = RecoveryManager(mock=dry_run)

            # Get list of datasets that will be affected
            datasets_to_snapshot = list(all_current.keys())  # Snapshot existing datasets

            if datasets_to_snapshot:
                try:
                    checkpoint = recovery.create_checkpoint(
                        datasets=datasets_to_snapshot,
                        name="pre-apply"
                    )
                    print_success(console, "Checkpoint created")
                    console.print(f"  [dim]Snapshots: {len(checkpoint.get('snapshots', {}))} dataset(s)[/dim]")
                    console.print("  [dim]Config backups: storage.cfg, smb.conf[/dim]")
                except Exception as e:
                    print_warning(console, f"Checkpoint creation failed: {e}")
                    print_warning(console, "Continuing without checkpoint (use --no-checkpoint to suppress this warning)")
                    checkpoint = None
            else:
                console.print("[dim]No existing datasets to snapshot[/dim]")

        # Initialize safety guard
        from tengil.core.safety import get_safety_guard
        get_safety_guard(mock=dry_run)

        # Initialize state tracking
        state = StateStore()

        # Initialize permission manager (unified permission handling)
        permission_mgr = PermissionManager()

        # Initialize managers (pass permission_mgr for unified permission handling)
        zfs = ZFSManager(mock=dry_run, state_store=state, permission_manager=permission_mgr)
        proxmox = ProxmoxManager(mock=dry_run, permission_manager=permission_mgr)
        nas = NASManager(mock=dry_run, permission_manager=permission_mgr)

        # Apply changes using ChangeApplicator
        applicator = ChangeApplicator(zfs, proxmox, nas, state, console)
        
        # Debug: show what we're passing
        console.print(f"\n[dim]Debug: changes={len(changes)}, container_changes={len(engine.container_changes) if engine.container_changes else 0}[/dim]")
        
        applicator.apply_changes(changes, all_desired, container_changes=engine.container_changes)

        # Show state summary
        stats = state.get_stats()
        console.print("\n[cyan]State Summary:[/cyan]")
        console.print(f"  Datasets managed: {stats['datasets_managed']}")
        console.print(f"    Created by Tengil: {stats['datasets_created']}")
        console.print(f"    Pre-existing: {stats['datasets_external']}")
        console.print(f"  Containers managed: {stats.get('containers_managed', 0)}")
        if stats.get('containers_created', 0) > 0:
            console.print(f"    Created by Tengil: {stats['containers_created']}")
        console.print(f"  Container mounts: {stats['mounts_managed']}")
        console.print(f"  SMB shares: {stats['smb_shares']}")
        console.print(f"  NFS exports: {stats['nfs_shares']}")
        console.print(f"\n[dim]State saved to: {state.state_file}[/dim]")

        print_success(console, "Apply complete")

        if checkpoint and not no_checkpoint:
            console.print(f"\n[dim]Recovery checkpoint available from {checkpoint['timestamp']}[/dim]")
            console.print(f"[dim]Use 'tg rollback --to {checkpoint['timestamp']}' if needed[/dim]")

    except Exception as err:
        print_error(console, f"Apply failed: {err}")

        # Attempt automatic rollback if checkpoint exists
        if checkpoint and recovery and not no_checkpoint:
            print_warning(console, "Attempting automatic rollback to checkpoint...")
            try:
                if recovery.rollback(checkpoint, force=True):
                    print_success(console, "Rollback successful")
                    print_warning(console, "Infrastructure restored to pre-apply state")
                else:
                    print_error(console, "Rollback completed with errors")
                    print_warning(console, "Manual intervention may be required")
                    console.print(f"[dim]Check logs at: {log_file or '/var/log/tengil/tengil.log'}[/dim]")
            except Exception as rollback_error:
                print_error(console, f"Rollback failed: {rollback_error}")
                print_warning(console, "Manual recovery required")
                console.print("\n[cyan]Manual recovery steps:[/cyan]")
                console.print("  1. Check ZFS snapshots: zfs list -t snapshot")
                console.print("  2. Rollback manually: zfs rollback <dataset>@tengil-pre-apply-*")
                console.print("  3. Check backups: ls /var/lib/tengil/backups/")
        else:
            print_warning(console, "No checkpoint available for automatic rollback")
            if verbose:
                console.print_exception()

        raise typer.Exit(1) from err


def register_state_commands(
    app: typer.Typer,
    shared_console: Console,
    shared_template_loader=None
):
    """Register state management commands with the main Typer app.

    Args:
        app: Main Typer application
        shared_console: Shared Rich console instance
        shared_template_loader: Not used here, for API consistency
    """
    global console
    console = shared_console

    # Register commands
    app.command()(scan)
    app.command()(verify)
    app.command()(diff)
    app.command(name="plan")(diff)  # Alias for terraform-style workflow
    app.command()(apply)
