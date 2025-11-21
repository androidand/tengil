"""Git integration CLI commands for config management."""
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

# Module-level console instance (will be set by register function)
console: Console = Console()


def _run_git_command(args: list, cwd: Optional[Path] = None) -> tuple[bool, str, str]:
    """Run a git command and return success, stdout, stderr."""
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout.strip(), result.stderr.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stdout.strip() if e.stdout else "", e.stderr.strip() if e.stderr else str(e)
    except FileNotFoundError:
        return False, "", "Git not found. Please install git first."


def _find_config_dir() -> Optional[Path]:
    """Find the directory containing tengil.yml."""
    current = Path.cwd()
    
    # Check current directory first
    if (current / "tengil.yml").exists():
        return current
    
    # Check parent directories
    for parent in current.parents:
        if (parent / "tengil.yml").exists():
            return parent
    
    return None


def init(
    repo_url: Optional[str] = typer.Option(None, "--repo", help="Remote repository URL to clone from"),
    path: Optional[str] = typer.Option(None, "--path", help="Directory path (default: current directory)"),
):
    """Initialize git repository for Tengil config management.
    
    Creates .gitignore with Tengil-specific patterns and optionally sets up remote.
    """
    from tengil.cli_support import print_error, print_info, print_success
    
    target_dir = Path(path) if path else Path.cwd()
    
    if repo_url:
        # Clone existing repository
        console.print(f"[dim]Cloning repository from {repo_url}...[/dim]")
        success, stdout, stderr = _run_git_command(['clone', repo_url, str(target_dir)])
        
        if not success:
            print_error(console, f"Failed to clone repository: {stderr}")
            raise typer.Exit(1)
        
        print_success(console, f"Repository cloned to {target_dir}")
        
        # Check if tengil.yml exists
        if not (target_dir / "tengil.yml").exists():
            print_info(console, "No tengil.yml found in repository. Run 'tg init --package <name>' to create one.")
        
        return
    
    # Initialize new repository
    if not (target_dir / ".git").exists():
        console.print("[dim]Initializing git repository...[/dim]")
        success, stdout, stderr = _run_git_command(['init'], cwd=target_dir)
        
        if not success:
            print_error(console, f"Failed to initialize git repository: {stderr}")
            raise typer.Exit(1)
        
        print_success(console, "Git repository initialized")
    else:
        print_info(console, "Git repository already exists")
    
    # Create .gitignore if it doesn't exist
    gitignore_path = target_dir / ".gitignore"
    gitignore_content = """# Tengil state and logs
.tengil.state.json
.tengil.state.json.backup
tengil.log
*.log

# Temporary files
*.tmp
*.bak
.DS_Store
Thumbs.db

# IDE files
.vscode/
.idea/
*.swp
*.swo

# Python cache (if using custom scripts)
__pycache__/
*.pyc
*.pyo
"""
    
    if not gitignore_path.exists():
        gitignore_path.write_text(gitignore_content)
        print_success(console, "Created .gitignore with Tengil patterns")
    else:
        print_info(console, ".gitignore already exists")
    
    # Add initial files if tengil.yml exists
    if (target_dir / "tengil.yml").exists():
        success, stdout, stderr = _run_git_command(['add', 'tengil.yml', '.gitignore'], cwd=target_dir)
        if success:
            print_info(console, "Added tengil.yml and .gitignore to git")
        else:
            print_error(console, f"Failed to add files: {stderr}")


def status():
    """Show git status for Tengil config directory."""
    from tengil.cli_support import print_error, print_info
    
    config_dir = _find_config_dir()
    if not config_dir:
        print_error(console, "No tengil.yml found in current directory or parents")
        raise typer.Exit(1)
    
    if not (config_dir / ".git").exists():
        print_error(console, f"No git repository found in {config_dir}")
        print_info(console, "Run 'tg git init' to initialize git repository")
        raise typer.Exit(1)
    
    success, stdout, stderr = _run_git_command(['status', '--porcelain'], cwd=config_dir)
    
    if not success:
        print_error(console, f"Git status failed: {stderr}")
        raise typer.Exit(1)
    
    if not stdout:
        console.print("[green]✓ Working directory clean[/green]")
        return
    
    console.print("[yellow]Modified files:[/yellow]")
    for line in stdout.split('\n'):
        if line.strip():
            status_code = line[:2]
            filename = line[3:]
            
            if status_code == "??":
                console.print(f"  [red]?[/red] {filename} (untracked)")
            elif status_code[0] == "M":
                console.print(f"  [yellow]M[/yellow] {filename} (modified)")
            elif status_code[0] == "A":
                console.print(f"  [green]A[/green] {filename} (added)")
            elif status_code[0] == "D":
                console.print(f"  [red]D[/red] {filename} (deleted)")
            else:
                console.print(f"  {status_code} {filename}")


def commit(
    message: str = typer.Option(..., "--message", "-m", help="Commit message"),
    add_all: bool = typer.Option(False, "--all", "-a", help="Add all modified files before commit"),
):
    """Commit changes to Tengil configuration."""
    from tengil.cli_support import print_error, print_success
    
    config_dir = _find_config_dir()
    if not config_dir:
        print_error(console, "No tengil.yml found in current directory or parents")
        raise typer.Exit(1)
    
    if not (config_dir / ".git").exists():
        print_error(console, f"No git repository found in {config_dir}")
        raise typer.Exit(1)
    
    # Add files if requested
    if add_all:
        success, stdout, stderr = _run_git_command(['add', '-A'], cwd=config_dir)
        if not success:
            print_error(console, f"Failed to add files: {stderr}")
            raise typer.Exit(1)
    
    # Commit changes
    success, stdout, stderr = _run_git_command(['commit', '-m', message], cwd=config_dir)
    
    if not success:
        if "nothing to commit" in stderr:
            console.print("[yellow]No changes to commit[/yellow]")
            return
        else:
            print_error(console, f"Commit failed: {stderr}")
            raise typer.Exit(1)
    
    print_success(console, f"Changes committed: {message}")


def push(
    remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
    branch: str = typer.Option("main", "--branch", "-b", help="Branch name"),
):
    """Push commits to remote repository."""
    from tengil.cli_support import print_error, print_success
    
    config_dir = _find_config_dir()
    if not config_dir:
        print_error(console, "No tengil.yml found in current directory or parents")
        raise typer.Exit(1)
    
    if not (config_dir / ".git").exists():
        print_error(console, f"No git repository found in {config_dir}")
        raise typer.Exit(1)
    
    console.print(f"[dim]Pushing to {remote}/{branch}...[/dim]")
    success, stdout, stderr = _run_git_command(['push', remote, branch], cwd=config_dir)
    
    if not success:
        print_error(console, f"Push failed: {stderr}")
        raise typer.Exit(1)
    
    print_success(console, f"Changes pushed to {remote}/{branch}")


def register_git_commands(
    app: typer.Typer,
    shared_console: Console,
    shared_template_loader=None
):
    """Register git commands with the main Typer app.

    Args:
        app: Main Typer application
        shared_console: Shared Rich console instance
        shared_template_loader: Not used here, for API consistency
    """
    global console
    console = shared_console

    # Create git subcommand group
    git_app = typer.Typer(help="Git integration for config management")
    
    # Register commands
    git_app.command()(init)
    git_app.command()(status)
    git_app.command()(commit)
    git_app.command()(push)
    
    # Add to main app
    app.add_typer(git_app, name="git")