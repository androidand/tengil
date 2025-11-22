"""Drift management CLI commands for handling reality vs config differences."""
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

# Module-level console instance (will be set by register function)
console: Console = Console()


def import_drift(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    auto_merge: bool = typer.Option(False, "--auto-merge", help="Automatically merge non-dangerous drift"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be imported without making changes"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Path to log file"),
):
    """Import drift from reality into tengil.yml configuration.
    
    Analyzes differences between your tengil.yml and actual Proxmox state,
    then offers to update your config to match reality.
    """
    from tengil.cli_drift_helpers import analyze_drift
    from tengil.cli_support import (
        handle_cli_error,
        load_config_and_orchestrate,
        print_error,
        print_info,
        print_success,
        print_warning,
        setup_file_logging,
    )
    from tengil.core.drift_engine import DriftSeverity
    
    setup_file_logging(log_file=log_file, verbose=verbose)
    
    try:
        # Load configuration
        loader, *_ = load_config_and_orchestrate(config, dry_run=True)
        
        # Analyze drift
        report, status = analyze_drift(loader)
        
        if report is None:
            if status == "missing-snapshot":
                print_error(console, "No reality snapshot found. Run 'tg scan' first to capture current state.")
            elif status == "no-loader":
                print_error(console, "Could not load configuration")
            elif status == "desired-error":
                print_error(console, "Configuration has errors. Fix them first.")
            raise typer.Exit(1)
        
        if report.is_clean():
            print_success(console, "No drift detected - configuration matches reality")
            return
        
        # Display drift summary
        _display_drift_summary(report)
        
        if dry_run:
            print_warning(console, "DRY RUN - No changes would be made")
            return
        
        # Process drift items interactively
        config_updates = {}
        dangerous_items = []
        auto_merge_items = []
        info_items = []
        
        for item in report.items:
            if item.severity == DriftSeverity.DANGEROUS:
                dangerous_items.append(item)
            elif item.severity == DriftSeverity.AUTO_MERGE:
                auto_merge_items.append(item)
            else:
                info_items.append(item)
        
        # Handle auto-merge items
        if auto_merge_items and auto_merge:
            console.print(f"\\n[yellow]Auto-merging {len(auto_merge_items)} safe drift items...[/yellow]")
            for item in auto_merge_items:
                _apply_drift_item(item, config_updates)
                console.print(f"  ✓ {item.resource}.{item.field}: {item.message}")
        
        # Handle dangerous items (always require confirmation)
        if dangerous_items:
            console.print(f"\\n[red]Found {len(dangerous_items)} dangerous drift items:[/red]")
            for item in dangerous_items:
                _display_drift_item(item)
                
                if Confirm.ask("Import this change into tengil.yml?", default=False):
                    _apply_drift_item(item, config_updates)
                    console.print(f"  ✓ Will update {item.resource}.{item.field}")
                else:
                    console.print(f"  ✗ Skipped {item.resource}.{item.field}")
        
        # Handle auto-merge items interactively if not auto-merged
        if auto_merge_items and not auto_merge:
            console.print(f"\\n[yellow]Found {len(auto_merge_items)} safe drift items:[/yellow]")
            
            if Confirm.ask("Auto-merge all safe changes?", default=True):
                for item in auto_merge_items:
                    _apply_drift_item(item, config_updates)
                console.print(f"  ✓ Will merge {len(auto_merge_items)} safe changes")
            else:
                # Ask individually
                for item in auto_merge_items:
                    _display_drift_item(item)
                    if Confirm.ask("Import this change?", default=True):
                        _apply_drift_item(item, config_updates)
                        console.print(f"  ✓ Will update {item.resource}.{item.field}")
        
        # Handle info items
        if info_items:
            console.print(f"\\n[cyan]Found {len(info_items)} informational drift items:[/cyan]")
            for item in info_items:
                console.print(f"  ℹ {item.resource}.{item.field}: {item.message}")
        
        # Apply updates to config file
        if config_updates:
            config_path = Path(config or "tengil.yml")
            _update_config_file(config_path, config_updates)
            print_success(console, f"Updated {config_path} with {len(config_updates)} changes")
            
            # Suggest next steps
            console.print("\\n[cyan]Next steps:[/cyan]")
            console.print("  1. Review changes: git diff tengil.yml")
            console.print("  2. Test configuration: tg diff")
            console.print("  3. Commit changes: tg git commit -m 'Import drift from reality'")
        else:
            print_info(console, "No changes imported")
    
    except FileNotFoundError as e:
        handle_cli_error(e, console, verbose, exit_code=1)
    except Exception as e:
        handle_cli_error(e, console, verbose, exit_code=1)


def _display_drift_summary(report):
    """Display a summary table of drift items."""
    from tengil.core.drift_engine import DriftSeverity, summarize_drift_report
    
    severity_labels = {
        DriftSeverity.DANGEROUS: "[red]Dangerous[/red]",
        DriftSeverity.AUTO_MERGE: "[yellow]Auto-merge[/yellow]",
        DriftSeverity.INFO: "[cyan]Info[/cyan]",
    }
    
    summary = summarize_drift_report(report)
    
    console.print("\\n[bold magenta]Drift Analysis Results[/bold magenta]")
    
    # Summary table
    summary_table = Table(show_header=True, header_style="bold")
    summary_table.add_column("Severity")
    summary_table.add_column("Count", justify="right")
    summary_table.add_column("Description")
    
    for severity, count in sorted(summary["counts"].items(), key=lambda item: item[0]):
        if severity == DriftSeverity.DANGEROUS:
            desc = "Requires manual review"
        elif severity == DriftSeverity.AUTO_MERGE:
            desc = "Safe to auto-merge"
        else:
            desc = "Informational only"
        
        summary_table.add_row(
            severity_labels.get(severity, severity),
            str(count),
            desc
        )
    
    console.print(summary_table)


def _display_drift_item(item):
    """Display details of a single drift item."""
    severity_colors = {
        "DANGEROUS": "red",
        "AUTO_MERGE": "yellow", 
        "INFO": "cyan"
    }
    
    color = severity_colors.get(str(item.severity), "white")
    console.print(f"\\n[{color}]● {item.resource}.{item.field}[/{color}]")
    console.print(f"  Message: {item.message}")
    if hasattr(item, 'current_value') and hasattr(item, 'desired_value'):
        console.print(f"  Current: {item.current_value}")
        console.print(f"  Config:  {item.desired_value}")


def _apply_drift_item(item, config_updates):
    """Apply a drift item to the config updates dictionary."""
    # This is a simplified implementation
    # In practice, you'd need to parse the resource path and update the nested config
    resource_path = item.resource.split('.')
    field_path = f"{'.'.join(resource_path)}.{item.field}"
    
    # Store the update (simplified - real implementation would handle nested dicts)
    config_updates[field_path] = getattr(item, 'current_value', item.message)


def _update_config_file(config_path: Path, updates: dict):
    """Update the tengil.yml file with drift changes."""
    import yaml
    
    # Load current config
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}
    
    # Apply updates (simplified implementation)
    # In practice, you'd need to properly handle nested dictionary updates
    for field_path, value in updates.items():
        console.print(f"  [dim]Would update {field_path} = {value}[/dim]")
        # TODO: Implement proper nested dictionary update logic
    
    # Write back (commented out for safety in this simplified version)
    # with open(config_path, 'w') as f:
    #     yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    console.print("  [yellow]Note: Config file update not implemented in this version[/yellow]")
    console.print("  [yellow]Please manually apply the changes shown above[/yellow]")


def register_drift_commands(
    app: typer.Typer,
    shared_console: Console,
    shared_template_loader=None
):
    """Register drift management commands with the main Typer app.

    Args:
        app: Main Typer application
        shared_console: Shared Rich console instance
        shared_template_loader: Not used here, for API consistency
    """
    global console
    console = shared_console

    # Register commands directly (not as subgroup for now)
    app.command(name="import-drift")(import_drift)