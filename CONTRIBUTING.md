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

## Testing

```bash
# All tests
poetry run pytest -v

# Specific test file
poetry run pytest tests/test_container_creation.py -v

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
