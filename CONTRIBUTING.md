# Contributing to Tengil

Thank you for your interest in contributing to Tengil! This guide will help you get started.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/androidand/tengil.git
cd tengil

# Set up development environment
python3 -m venv .venv
source .venv/bin/activate
pip install poetry
poetry install

# Run tests
poetry run pytest tests/test_integration.py -v

# Test in mock mode
TG_MOCK=1 poetry run tg init --datasets media
TG_MOCK=1 poetry run tg diff
TG_MOCK=1 poetry run tg apply --yes
```

## Development Workflow

1. **Pick an issue** from the [roadmap](ROADMAP.md) or [issues](https://github.com/androidand/tengil/issues)
2. **Comment** that you're working on it
3. **Create a branch**: `git checkout -b feature/your-feature`
4. **Write code** with tests
5. **Run tests**: `poetry run pytest -v`
6. **Test manually** in mock mode
7. **Commit**: Use conventional commits (`feat:`, `fix:`, `docs:`, etc.)
8. **Push** and create a Pull Request

## Code Style

- **Python**: Follow PEP 8, use type hints
- **Formatting**: Run `black .` before committing
- **Linting**: Run `ruff check .`
- **Tests**: Every feature needs tests in `tests/test_integration.py`

## Testing

### Mock Mode
Always test in mock mode first:

```bash
export TG_MOCK=1
poetry run tg init --datasets test
poetry run tg apply --yes
```

### Integration Tests
Add tests for new features:

```python
# tests/test_integration.py
class TestYourFeature:
    """Test your new feature."""
    
    def test_feature_works(self, temp_dir):
        """Test that your feature does what it should."""
        # Setup
        # Execute
        # Assert
```

### Running Tests
```bash
# All tests
poetry run pytest tests/ -v

# Specific test
poetry run pytest tests/test_integration.py::TestYourFeature -v

# With coverage
poetry run pytest --cov=tengil tests/
```

## Documentation

Update documentation when adding features:

- **README.md**: User-facing features and usage
- **ROADMAP.md**: Implementation status
- **Code**: Docstrings for all public functions

## What to Contribute

Check [ROADMAP.md](ROADMAP.md) for planned features. Priority areas:

### 🔴 Critical (Help Wanted!)
- Snapshot management & rollback
- Explicit delete mode
- Import existing infrastructure

### 🟡 High Priority
- Health check command
- Profile library expansion
- Cluster awareness

### 🟢 Medium Priority
- Web UI/dashboard
- Advanced share configs
- Monitoring integration

### 🎨 Always Welcome
- Bug fixes
- Documentation improvements
- Test coverage
- Profile contributions
- Example configurations

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add snapshot management command
fix: handle missing container gracefully
docs: update README with rollback instructions
test: add tests for nested datasets
refactor: extract snapshot logic to manager class
```

## Pull Request Process

1. **Update tests** - All features need tests
2. **Update docs** - Document new features in README
3. **Run tests locally** - Must pass before PR
4. **Describe changes** - Clear PR description with examples
5. **Link issues** - Reference related issues

## Code Review

PRs will be reviewed for:
- ✅ Tests pass
- ✅ Code style (black, ruff)
- ✅ Documentation updated
- ✅ Feature matches specification
- ✅ No breaking changes (or clearly noted)

## Questions?

- **Discussions**: Use GitHub Discussions for questions
- **Bugs**: Open an issue with reproduction steps
- **Features**: Open an issue with use case description

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Happy coding! 🚀
