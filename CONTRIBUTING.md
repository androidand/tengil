# Contributing to Tengil

Thank you for your interest in contributing!

## Quick Start

```bash
git clone https://github.com/androidand/tengil.git
cd tengil
poetry install
poetry run pytest -v
```

## Development Process

1. Check [ROADMAP.md](ROADMAP.md) for current priorities
2. Create a branch: `git checkout -b feature/your-feature`
3. Write code with tests
4. Run tests: `poetry run pytest -v`
5. Commit with conventional format: `feat:`, `fix:`, `docs:`, etc.
6. Create a Pull Request

## CLI Architecture

Tengil uses a modular CLI architecture for maintainability:

### File Organization

```
tengil/
├── cli.py                          # Bootstrap (42 lines) - wires modules together
├── cli_core_commands.py            # Infrastructure operations (diff, apply, init)
├── cli_container_commands.py       # Container lifecycle (exec, start, stop)
├── cli_app_commands.py             # App repository management (sync, list)
├── cli_compose_commands.py         # Docker Compose analysis
├── cli_discover_commands.py        # Discovery commands
├── cli_env_commands.py             # Environment variable management
├── cli_support.py                  # Shared utilities and helpers
├── cli_discover_helpers.py         # Docker discovery rendering
└── cli_container_resolution.py     # Container name/VMID resolution

tests/
├── test_cli_support.py             # Helper function tests
├── test_cli_container.py           # Container command tests
├── test_cli_app.py                 # App command tests
└── test_cli_help.py                # Help output snapshot tests
```

### Adding New Commands

See [.local/CLI_DEVELOPER_GUIDE.md](.local/CLI_DEVELOPER_GUIDE.md) for detailed patterns and examples.

**Quick Example** - Add a command to existing group:

```python
# In tengil/cli_container_commands.py
@ContainerTyper.command("logs")
def logs_command(
    target: str = typer.Argument(..., help="Container target"),
    tail: int = typer.Option(50, "--tail", help="Lines to show"),
) -> None:
    """Show container logs."""
    from tengil.cli_support import print_success

    resolved = resolve_container_target(target)
    lifecycle = ContainerLifecycle(mock=is_mock())
    lifecycle.show_logs(resolved.vmid, tail=tail)
    print_success(console, f"Displayed logs for {resolved.name}")
```

**Then add tests** in `tests/test_cli_container.py`:

```python
def test_container_logs(monkeypatch):
    monkeypatch.setenv('TG_MOCK', '1')
    result = runner.invoke(app, ['container', 'logs', 'jellyfin', '--tail', '100'])
    assert result.exit_code == 0
```

### Design Principles

- **Single Responsibility**: Each module has one clear purpose
- **Shared Utilities**: Use helpers from `cli_support.py` for consistency
- **Container Resolution**: Always use `resolve_container_target()` for container lookups
- **Output Formatting**: Use `print_success/error/warning/info` helpers
- **Mock Awareness**: Check `is_mock()` for test-friendly behavior

## Testing

```bash
# All tests
poetry run pytest -v

# Specific test file
poetry run pytest tests/test_container_creation.py -v

# CLI tests
poetry run pytest tests/test_cli_support.py tests/test_cli_container.py tests/test_cli_app.py -v

# CLI smoke tests (requires dependencies)
./scripts/test-cli.sh

# Mock mode (for manual testing)
export TG_MOCK=1
poetry run tg diff
```

## Requirements

- All features need tests
- Update docs if adding user-facing features
- Tests must pass before PR

## Questions?

- Check [ROADMAP.md](ROADMAP.md) for project direction
- Open an issue for bugs or feature requests
- Use GitHub Discussions for questions

## License

MIT License - see LICENSE file.
