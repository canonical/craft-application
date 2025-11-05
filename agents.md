# Agents Guide

This guide helps AI coding agents and automation tools work effectively with the craft-application repository.

## Overview

**craft-application** is a Python library that serves as the base framework for all Starcraft applications (like snapcraft, charmcraft, etc.). It provides common mechanisms for application services, project models, and other shared functionality.

- **Language**: Python 3.10+
- **License**: LGPL-3.0
- **Build System**: setuptools with setuptools_scm
- **Package Manager**: uv
- **Documentation**: See [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md)

## Development Workflow

### Initial Setup

1. **Clone the repository** (see [CONTRIBUTING.md](CONTRIBUTING.md) for details):

    ```bash
    git clone https://github.com/canonical/craft-application --recurse-submodules
    cd craft-application
    ```

2. **Set up the development environment**:

    ```bash
    make setup
    ```

    This installs all dependencies, sets up the virtual environment, and configures pre-commit hooks.

3. **Verify the setup**:
    ```bash
    make lint
    make test
    ```

### Common Development Tasks

Use these `make` targets for everyday development. Run `make help` to see all available targets.

#### Formatting Code

```bash
make format                # Run all automatic formatters
make format-ruff           # Format with ruff only
make format-codespell      # Fix spelling issues
make format-prettier       # Format YAML/JSON/Markdown files
```

#### Linting Code

```bash
make lint                  # Run all linters
make lint-ruff             # Lint with ruff
make lint-mypy             # Type check with mypy
make lint-pyright          # Type check with pyright
make lint-codespell        # Check spelling
make lint-docs             # Lint documentation
make lint-prettier         # Check YAML/JSON/Markdown formatting
make lint-shellcheck       # Lint shell scripts
```

#### Running Tests

```bash
make test                  # Run all tests
make test-fast             # Run fast tests only (excludes tests marked as 'slow')
make test-slow             # Run slow tests only
make test-coverage         # Generate coverage report
```

#### Building Documentation

```bash
make docs                  # Build documentation
make docs-auto             # Build and auto-reload docs at localhost:8080
```

#### Cleaning Up

```bash
make clean                 # Remove build artifacts and temporary files
```

### Pre-commit Hooks

This project uses pre-commit hooks that run automatically on `git commit`. They include:

- Ruff linting and formatting
- Prettier formatting for YAML/JSON/Markdown
- Trailing whitespace removal
- End-of-file fixer
- Various file checks

See [.pre-commit-config.yaml](.pre-commit-config.yaml) for the full configuration.

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/) style:

```
<type>: <description>

[optional body]

[optional footer]
```

Common types (in priority order):

- `ci`: CI/CD changes
- `build`: Build system changes
- `feat`: New features
- `fix`: Bug fixes
- `perf`: Performance improvements
- `refactor`: Code refactoring
- `style`: Code style changes
- `test`: Test changes
- `docs`: Documentation changes
- `chore`: Maintenance tasks

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details on commit conventions.

## Project Structure

```
craft_application/
├── commands/          # CLI command implementations
├── git/              # Git integration utilities
├── launchpad/        # Launchpad integration for remote builds
├── misc/             # Miscellaneous utilities
├── models/           # Pydantic data models
├── remote/           # Remote build support
├── services/         # Application services (lifecycle, package, etc.)
├── util/             # General utility functions
├── application.py    # Main Application class
├── errors.py         # Custom exceptions
└── fetch.py          # File fetching utilities

tests/
├── unit/             # Unit tests (mirror craft_application structure)
├── integration/      # Integration tests
├── spread/           # Spread system tests
└── data/             # Test data and fixtures
```

## Testing Guidelines

### Test Organization

- **Unit tests**: In `tests/unit/` - mirror the structure of `craft_application/`
- **Integration tests**: In `tests/integration/` - test component interactions
- **Spread tests**: In `tests/spread/` - system-level tests using the Spread framework

### Writing Tests

- Use pytest for unit and integration tests
- Follow existing test patterns in the repository
- Add tests for all non-trivial code changes
- Mark slow tests with `@pytest.mark.slow` decorator
- Use fixtures and mocks appropriately

### Running Specific Tests

```bash
# Run tests in a specific file
uv run pytest tests/unit/test_application.py

# Run tests matching a pattern
uv run pytest -k "test_pattern"

# Run with verbose output
uv run pytest -v

# Run in parallel (if pytest-xdist is available)
uv run pytest -n auto
```

## Code Quality Standards

### Type Checking

- All code in `craft_application/` must be fully type-annotated
- Uses both mypy and pyright for type checking
- Configuration in `pyproject.toml` under `[tool.mypy]` and `[tool.pyright]`

### Linting

- **Ruff**: Primary linter and formatter (replaces flake8, black, isort)
    - Line length: 88 characters
    - Target: Python 3.10+
    - Configuration in `pyproject.toml` under `[tool.ruff]`
- **Codespell**: Spell checking
- **Prettier**: For YAML, JSON, and Markdown files

### Code Style

- Follow PEP 8 conventions
- Use type hints for all function parameters and return values
- Add docstrings for public APIs (Google/NumPy style)
- Keep functions focused and testable
- Prefer composition over inheritance

## Dependencies

### Adding Dependencies

1. Add the dependency to `pyproject.toml` under `[project.dependencies]`
2. For development-only dependencies, add to `[dependency-groups]`
3. Update the lock file: `uv lock`
4. Test that it works: `make setup && make test`

### Dependency Groups

- `dev`: Core development dependencies (pytest, coverage, etc.)
- `lint`: Linting tools
- `types`: Type checking tools (mypy, type stubs)
- `docs`: Documentation tools (Sphinx, etc.)
- `remote`: Optional remote-build support (launchpadlib)
- `apt`: Optional python-apt support

## Common Patterns

### Working with Services

Services in `craft_application/services/` follow a consistent pattern:

- Inherit from appropriate base classes
- Use dependency injection
- Implement well-defined interfaces
- Are tested in isolation with mocks

### Working with Models

Pydantic models in `craft_application/models/`:

- Use Pydantic v2 syntax
- Include validators where appropriate
- Provide clear docstrings
- Support serialization/deserialization

### Error Handling

Custom exceptions in `craft_application/errors.py`:

- Inherit from `CraftError` or appropriate subclass
- Include clear error messages
- Provide context for debugging

## Continuous Integration

GitHub Actions workflows are in `.github/workflows/`:

- `qa.yaml`: Main quality assurance (lint, type check, test)
- `spread.yaml`: Spread integration tests
- `tics.yaml`: TICS quality analysis
- `policy.yaml`: Security and policy checks
- `release-publish.yaml`: Release automation

## Documentation

### Building Docs

```bash
make docs          # Build static documentation
make docs-auto     # Build with live reload
make lint-docs     # Check documentation quality
```

### Documentation Structure

- Source: `docs/` directory
- Common docs: `docs/common/` (shared with downstream apps)
- Built docs: `docs/_build/` (gitignored)
- Uses Sphinx with canonical-sphinx theme
- Follows Diátaxis framework (tutorials, how-to, reference, explanation)

## Tips for Agents

1. **Always run setup first**: `make setup` ensures a clean development environment
2. **Test incrementally**: Run `make test-fast` during development, `make test` before committing
3. **Format before committing**: `make format` or rely on pre-commit hooks
4. **Check types early**: Run `make lint-mypy lint-pyright` to catch type errors
5. **Reference existing code**: Look at similar implementations for patterns and style
6. **Read CONTRIBUTING.md**: Contains detailed guidelines for contributors
7. **Use uv commands directly**: For fine-grained control, use `uv run <command>`
8. **Clean when stuck**: `make clean && rm -rf .venv && make setup` for a fresh start

## Important Notes

- **Minimal changes**: Make the smallest possible changes to achieve the goal
- **Don't remove working code**: Unless fixing a bug or security issue in changed code
- **Update docs**: If changing public APIs or adding features
- **Test all changes**: Don't skip tests even for "simple" changes
- **Follow conventions**: Match the style and patterns of existing code
- **Version pinning**: Be cautious with dependency versions (see pygit2 comments in pyproject.toml)

## Getting Help

- **Documentation**: https://canonical-craft-application.readthedocs-hosted.com/
- **Issues**: https://github.com/canonical/craft-application/issues
- **Matrix Chat**: #starcraft-development:ubuntu.com
- **Code of Conduct**: https://ubuntu.com/community/ethos/code-of-conduct

## Future Considerations

_Note: The maintainer (@lengau) requested to tackle specific pain points and constraints later. This section is a placeholder for that future documentation._

Areas to document:

- Common pitfalls when working with craft-application
- Breaking change patterns to avoid
- Complex dependency constraints
- Platform-specific considerations
- Performance optimization guidelines
